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


class NumProxy:

    def __add__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__add__(other)

    def __sub__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__sub__(other)

    def __mul__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__mul__(other)

    def __floordiv__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__floordiv__(other)

    def __mod__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__mod__(other)

    def __and__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__and__(other)

    def __or__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__or__(other)

    def __xor__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__xor__(other)

    def __rshift__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__rshift__(other)

    def __lshift__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__lshift__(other)

    def __lt__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__lt__(other)

    def __le__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__le__(other)

    def __ge__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__ge__(other)

    def __gt__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__gt__(other)

    def __eq__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__eq__(other)

    def __ne__(self, other):
        if isinstance(other, NumProxy):
            other = other.value
        return self.value.__ne__(other)

    def __bool__(self):
        return self.value.__bool__()

    def __float__(self):
        return self.value.__float__()

    def __neg__(self):
        return self.value.__neg__()

    def __pos__(self):
        return self.value.__pos__()

    def __abs__(self):
        return self.value.__abs__()

    def __invert__(self):
        return self.value.__invert__()

    def __index__(self):
        return self.value.__index__()
