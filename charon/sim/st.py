#  -*- coding: utf-8 -*-
# *****************************************************************************
# Python/ST language tools
# Copyright (c) 2016 by the contributors (see AUTHORS)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************

import sys
import time
import struct
import itertools
import threading
import collections

from .srv import Server
from .util import NumProxy


class Memory(object):
    # XXX: not multi-PLC-safe!
    # Allocates addresses for variables.

    def __init__(self):
        # dyn is at 0x00000
        # %M* is at 0x10000
        # %I* is at 0x20000
        # %Q* is at 0x30000
        self.dyn_addr = 0
        self.allocations = []
        self.allocations_sorted = False

    def new(self, size):
        addr = self.dyn_addr
        self.dyn_addr += size
        return addr

    def map(self, addr, obj):
        """Map a new allocation."""
        self.allocations.append((obj.sizeof(), addr, obj))
        self.allocations_sorted = False

    def get(self, addr, size):
        """Return the object that addr belongs to, and the offset in it,
        if there are at least size bytes left.
        """
        if not self.allocations_sorted:
            self.allocations.sort(key=lambda x: x[1])
            self.allocations_sorted = True
        for (osize, oaddr, obj) in self.allocations:
            if oaddr <= addr and addr + size <= oaddr + osize:
                return (obj, addr - oaddr)
        raise RuntimeError('no value or addressing across value boundary')

    def read(self, addr, size):
        """Read memory."""
        (obj, offset) = self.get(addr, size)
        return obj.mem_read()[offset:offset+size]

    def write(self, addr, data):
        """Write memory."""
        (obj, offset) = self.get(addr, len(data))
        obj.mem_write(offset, data)


mem = Memory()


class Value(object):
    """Represents a place in memory for a variable."""

    @classmethod
    def alloc(cls, value, at=None):
        """Allocates an address for the value (if not given)."""
        if at is None:
            at = mem.new(cls.sizeof())
        val = cls(value, at)
        mem.map(at, val)
        return val

    @classmethod
    def default(cls, at=None):
        """Allocates a value with a default value."""
        return cls.alloc(cls.DEFAULT, at)

    @classmethod
    def unwrap(cls, value):
        """Retrieves the inner value from an rvalue assigned to this lvalue."""
        if isinstance(value, cls):
            return value.value
        return value

    @classmethod
    def sizeof(cls):
        """Returns the size of the value in memory."""
        raise NotImplementedError

    def __init__(self, value, addr):
        self.addr = addr
        self.assign(value)

    def __repr__(self):
        return repr(self.value)

    def assign(self, value):
        self.value = self.__class__.unwrap(value)

    def mem_read(self):
        raise NotImplementedError

    def mem_write(self, offset, data):
        raise NotImplementedError


class Integral(NumProxy, Value):
    DEFAULT = 0
    WIDTH = 0
    SIGNED = False
    MEMFMT = ''

    @classmethod
    def sizeof(cls):
        return cls.WIDTH // 8

    @classmethod
    def unwrap(cls, value):
        if isinstance(value, Integral):
            value = value.value
        limit = 1 << cls.WIDTH
        value %= limit
        if cls.SIGNED and value >= limit//2:
            value -= limit
        # if cls.SIGNED:
        #     limit = 1 << (cls.WIDTH - 1)
        #     if not -limit <= value < limit:
        #         raise RuntimeError('out of range assignment to %s: %s' % (
        #             cls.__name__, value))
        # else:
        #     if value < 0 or value >= 1 << cls.WIDTH:
        #         raise RuntimeError('out of range assignment to %s: %s' % (
        #             cls.__name__, value))
        return value

    def mem_read(self):
        return struct.pack(self.MEMFMT, self.value)

    def mem_write(self, offset, data):
        if offset != 0:
            raise RuntimeError('partial number write')
        self.value, = struct.unpack(self.MEMFMT, data)

    def __getitem__(self, i):
        # Bit access: a[[i]]
        return (self.value >> i[0]) & 1

    def __setitem__(self, i, val):
        mask = ~(1 << i[0])
        self.value = (self.value & mask) | ((val & 1) << i[0])


class byte(Integral):
    WIDTH = 8
    SIGNED = False
    MEMFMT = 'B'


class word(Integral):
    WIDTH = 16
    SIGNED = False
    MEMFMT = 'H'


class dword(Integral):
    WIDTH = 32
    SIGNED = False
    MEMFMT = 'I'


class bool(Integral):
    WIDTH = 1
    SIGNED = False
    MEMFMT = 'B'

    @classmethod
    def sizeof(cls):
        return 1


class real(NumProxy, Value):
    DEFAULT = 0.0

    @classmethod
    def sizeof(cls):
        return 4

    def mem_read(self):
        return struct.pack('f', self.value)

    def mem_write(self, offset, data):
        if offset != 0:
            raise RuntimeError('partial number write')
        self.value, = struct.unpack('f', data)


class anystring(Value):
    SLEN = 0
    DEFAULT = ''

    @classmethod
    def sizeof(cls):
        return cls.SLEN

    @classmethod
    def unwrap(cls, value):
        if isinstance(value, anystring):
            value = value.value
        if len(value) > cls.SLEN:
            raise RuntimeError('string too long (%d chars max)' % cls.SLEN)
        return value

    def mem_read(self):
        return self.value.encode() + b'\0' * (self.SLEN - len(self.value))

    def mem_write(self, offset, data):
        if offset != 0:
            raise RuntimeError('partial string write')
        self.value = data.split('\0', 1)[0]

    def __len__(self):
        return self.value.__len__()


def string(slen):
    return type('string_%d' % slen, (anystring,), dict(SLEN=slen))


class anyarray(Value):
    LENGTH = 0
    IMIN = 0
    INNER = None
    DEFAULT = []

    @classmethod
    def sizeof(cls):
        return cls.LENGTH * cls.INNER.sizeof()

    def __init__(self, value, addr):
        self.addr = addr
        self.value = []
        value = self.__class__.unwrap(value)
        step = self.INNER.sizeof()
        if len(value) > self.LENGTH:
            raise RuntimeError('too many values in array assignment')
        for i in range(self.LENGTH):
            self.value.append(self.INNER.alloc(
                value[i] if i < len(value) else self.INNER.DEFAULT,
                at=addr + i*step))

    def assign(self, value):
        raise RuntimeError('array assign')

    def __getitem__(self, i):
        if not self.IMIN <= i < self.IMIN + self.LENGTH:
            raise RuntimeError('array access out of range')
        return self.value[i - self.IMIN]

    def __setitem__(self, i, val):
        if not self.IMIN <= i < self.IMIN + self.LENGTH:
            raise RuntimeError('array access out of range')
        self.value[i - self.IMIN].assign(val)

    def __len__(self):
        return self.LENGTH

    def __repr__(self):
        return '<%s>' % (', '.join('%r' % x for x in self.value))

    def mem_read(self):
        return b''.join(v.mem_read() for v in self.value)

    def mem_write(self, offset, data):
        step = self.INNER.sizeof()
        if offset % step != 0:
            raise RuntimeError('partial array element write')
        if len(data) % step != 0:
            raise RuntimeError('partial array element write')
        i = offset // step
        while data:
            d, data = data[:step], data[step:]
            self.value[i].mem_write(0, d)
            i += 1


def array(innertype, imin, imax):
    length = imax - imin + 1
    return type('array_%d' % length, (anyarray,), dict(LENGTH=length,
                                                       IMIN=imin,
                                                       INNER=innertype))


class Var(object):
    """Represents a field in a struct."""

    def __init__(self, dtype, default=None, *, at=None):
        self.dtype = dtype
        self.default = default if default is not None else dtype.DEFAULT
        self.at = None  # XXX
        if at is not None:
            if at.startswith('%MB'):
                self.at = int(at[3:]) + 0x10000
            elif at.startswith('%IB'):
                self.at = int(at[3:]) + 0x20000
            elif at.startswith('%QB'):
                self.at = int(at[3:]) + 0x30000
            else:
                raise RuntimeError('addr spec %s not supported' % at)

    def __get__(self, obj, obj_class):
        if obj is None:
            return self
        return obj.__dict__[self]

    def __set__(self, obj, value):
        if obj is None:
            return
        obj.__dict__[self].assign(self.dtype.unwrap(value))


class StructMeta(type):
    @classmethod
    def __prepare__(self, name, bases):
        return collections.OrderedDict()

    def __init__(cls, name, bases, attrs):
        cls.VARS = []
        cls.OFFSET = {}
        size = 0
        for (name, var) in attrs.items():
            if isinstance(var, Var):
                cls.VARS.append((name, var))
                cls.OFFSET[name] = size
                # XXX alignment!
                size += var.dtype.sizeof()
        cls.SIZE = size


class Struct(Value, metaclass=StructMeta):
    DEFAULT = Ellipsis

    @classmethod
    def sizeof(cls):
        return cls.SIZE

    def __init__(self, value=None, addr=None, **pvars):
        self.addr = addr
        for (name, var) in self.VARS:
            self.__dict__[var] = var.dtype.alloc(
                getattr(value, name, pvars.pop(name, var.default)),
                at=var.at or (addr + self.OFFSET[name] if addr is not None else None))
        if pvars:
            raise RuntimeError('unknown variable in struct: %s' % pvars)

    def assign(self, value):
        if value is Ellipsis:
            # XXX set defaults necessary?
            # keep defaults
            return
        if isinstance(value, self.__class__):
            # XXX reassign individual values!
            raise RuntimeError('struct reassign')
        raise RuntimeError('trying to assign struct of wrong kind')

    def __repr__(self):
        items = []
        for (name, var) in self.VARS:
            items.append((name, self.__dict__[var]))
        return '%s { %s }' % (self.__class__.__name__,
                              ', '.join('%s => %r' % x for x in items))

    def mem_read(self):
        return b''.join(self.__dict__[var].mem_read() for (_, var) in self.VARS)

    def mem_write(self, offset, data):
        for (name, var) in self.VARS:
            ofs = self.OFFSET[name]
            size = var.dtype.sizeof()
            if ofs <= offset < ofs + size:
                # at least parial write
                # overlap
                o = min(ofs + size - offset, len(data))
                d, data = data[:o], data[o:]
                # (partial) write
                self.__dict__[var].mem_write(offset - ofs, d)
                if data:
                    self.mem_write(offset + o, data)
                return
        raise RuntimeError("failed to write %d bytes @ offset %d" %
                           (len(data), offset))


class Globals(Struct):
    pass


def program(**pvars):
    def deco(func):
        var_struct = type('%s_vars' % func.__name__, (Struct,), pvars)
        instance = var_struct()

        def new_func():
            func(instance)

        new_func.is_program = True
        return new_func
    return deco


def run(glob, mainfunc):
    if not isinstance(glob, Globals):
        raise RuntimeError('globals must be a Globals instance')
    if not getattr(mainfunc, 'is_program', False):
        raise RuntimeError('main function must be a program')

    cond = threading.Condition()
    srv = Server(mem, cond)
    threading.Thread(target=srv.serve_forever).start()

    print('Starting main PLC loop.')
    try:
        for i in itertools.count():
            if i % 100 == 0:
                print('\r%10d cycles' % i, end='')
                sys.stdout.flush()
            with cond:
                mainfunc()
                cond.notify()
            time.sleep(.005)
    except KeyboardInterrupt:
        srv.shutdown()
        sys.exit(0)
