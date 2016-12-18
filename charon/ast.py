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


class NodeMeta(type):
    def __init__(cls, name, bases, attrs):

        def init(self, **kwds):
            for (fld, spec) in cls.fields:
                if fld not in kwds:
                    raise TypeError('missing %s keyword in %s constructor' %
                                    (fld, cls.__name__))
                val = kwds.pop(fld)
                if isinstance(spec, list):
                    if not (isinstance(val, list) and
                            all(isinstance(v, spec[0]) for v in val)):
                        raise TypeError('%s constructor: %s should be list '
                                        'of %s' % (cls.__name__, fld,
                                                   spec[0].__name__))
                else:
                    if not isinstance(val, spec):
                        raise TypeError('%s constructor: %s should be %s' %
                                        (cls.__name__, fld, spec.__name__))
                setattr(self, fld, val)
            if kwds:
                raise TypeError('invalid keywords in %s constructor: %s' %
                                (cls.__name__, sorted(kwds)))

        cls.__init__ = init


class Node(metaclass=NodeMeta):

    def generate(self, out):
        raise NotImplementedError


# -- Expressions --------------------------------------------------------------

class Expr(Node):
    pass


class Id(Expr):
    fields = [
        ('id', str),
    ]

    def generate(self, out):
        out.push(self.id)


class Literal(Expr):
    pass


class Int(Literal):
    fields = [
        ('i', int),
    ]

    def generate(self, out):
        if self.i > 9:
            out.push('16#%x' % self.i)
        else:
            out.push('%d' % self.i)


class Float(Literal):
    fields = [
        ('f', float),
    ]

    def generate(self, out):
        out.push('%.8g' % self.f)


class Str(Literal):
    fields = [
        ('s', str),
    ]

    def generate(self, out):
        out.push(repr(self.s))


class List(Expr):
    fields = [
        ('exprs', [Expr]),
    ]

    def generate(self, out):
        out.push_sep(', ', self.exprs)


class UnOp(Expr):
    fields = [
        ('op', str),
        ('expr', Expr),
    ]

    def generate(self, out):
        # XXX handle parenthesification
        out.push(self.op)
        if self.op.isalpha():
            out.push(' ')
        out.push(self.expr)


class BinOp(Expr):
    fields = [
        ('left', Expr),
        ('op', str),
        ('right', Expr),
    ]

    def generate(self, out):
        # XXX handle parenthesification
        out.push(self.left)
        out.push(' %s ' % self.op)
        out.push(self.right)


class Call(Expr):
    fields = [
        ('base', Expr),
        ('args', [Expr]),
    ]

    def generate(self, out):
        out.push(self.base)
        out.push('(')
        out.push_sep(', ', self.args)
        out.push(')')


class Member(Expr):
    fields = [
        ('base', Expr),
        ('member', Expr),
    ]

    def generate(self, out):
        out.push(self.base)
        out.push('.')
        out.push(self.member)


class Subscript(Expr):
    fields = [
        ('base', Expr),
        ('sub', Expr),
    ]

    def generate(self, out):
        out.push(self.base)
        out.push('[')
        out.push(self.sub)
        out.push(']')


class KwArg(Node):
    fields = [
        ('name', str),
        ('value', Expr),
    ]

    def generate(self, out):
        out.push(self.name)
        out.push(':=')
        out.push(self.value)


class StructInitializer(Expr):
    fields = [
        ('fields', [KwArg]),
    ]

    def generate(self, out):
        out.push('(')
        out.push_sep(', ', self.fields)
        out.push(')')


# -- Data types ---------------------------------------------------------------

class Type(Node):
    pass


class SimpleType(Type):
    fields = [
        ('id', str),
    ]

    def generate(self, out):
        out.push(self.id)


class ArrayType(Type):
    fields = [
        ('imin', int),
        ('imax', int),
        ('inner', Type),
    ]

    def generate(self, out):
        out.push('ARRAY [%d..%d] OF ' % (self.imin, self.imax))
        out.push(self.inner)


class StringType(Type):
    fields = [
        ('length', int),
    ]

    def generate(self, out):
        out.push('STRING[%d]' % self.length)


class Var(Node):
    fields = [
        ('name', str),
        ('loc', [str]),
        ('type', Type),
        ('default', [Expr]),
    ]

    def generate(self, out):
        out.push(self.name)
        if self.loc:
            out.push(' AT %s' % self.loc[0])
        out.push(' : ')
        out.push(self.type)
        if self.default:
            out.push(' := ')
            out.push(self.default[0])
        out.push(';')


class VarBlock(Node):
    fields = [
        ('type', str),
        ('vars', [Var]),
    ]

    _ends = {'STRUCT': 'END_STRUCT'}

    def generate(self, out):
        out.push(self.type)
        out.more_indent()
        for var in self.vars:
            out.push_line(var)
        out.less_indent()
        out.push_line(self._ends.get(self.type, 'END_VAR'))


# -- Statements ---------------------------------------------------------------

class Stmt(Node):
    pass


class If(Stmt):
    fields = [
        ('expr', Expr),
        ('thens', [Stmt]),
        ('elses', [Stmt]),
    ]

    def generate(self, out, elsif=False):
        if not elsif:
            out.push('IF ')
        out.push(self.expr)
        out.push(' THEN')
        out.more_indent()
        for stmt in self.thens:
            out.push_line(stmt)
        out.less_indent()
        if len(self.elses) == 1 and isinstance(self.elses[0], If):
            out.push_line('ELSIF ')
            self.elses[0].generate(out, elsif=True)
        elif self.elses:
            out.push_line('ELSE')
            out.more_indent()
            for stmt in self.elses:
                out.push_line(stmt)
            out.less_indent()
        if not elsif:
            out.push_line('END_IF')


class CaseExpr(Node):
    pass


class CaseExprSingle(CaseExpr):
    fields = [
        ('expr', Expr),
    ]

    def generate(self, out):
        out.push(self.expr)


class CaseExprRange(CaseExpr):
    fields = [
        ('rfrom', Expr),
        ('rto', Expr),
    ]

    def generate(self, out):
        out.push(self.rfrom)
        out.push('..')
        out.push(self.rto)


class Case(Node):
    fields = [
        ('exprs', [CaseExpr]),
        ('stmts', [Stmt]),
    ]

    def generate(self, out):
        out.push_sep(', ', self.exprs)
        out.push(' :')
        out.more_indent()
        for stmt in self.stmts:
            out.push_line(stmt)
        out.less_indent()


class Switch(Stmt):
    fields = [
        ('expr', Expr),
        ('cases', [Case]),
        ('elses', [Stmt]),
    ]

    def generate(self, out):
        out.push('CASE ')
        out.push(self.expr)
        out.push(' OF')
        out.more_indent()
        for case in self.cases:
            out.push_line(case)
        out.less_indent()
        if self.elses:
            out.push_line('ELSE')
            out.more_indent()
            for stmt in self.elses:
                out.push_line(stmt)
            out.less_indent()
        out.push_line('END_CASE')


class While(Stmt):
    fields = [
        ('expr', Expr),
        ('stmts', [Stmt]),
    ]

    def generate(self, out):
        out.push('WHILE ')
        out.push(self.expr)
        out.push(' DO')
        out.more_indent()
        for stmt in self.stmts:
            out.push_line(stmt)
        out.less_indent()
        out.push_line('END_WHILE')


class Exit(Stmt):
    fields = [
    ]

    def generate(self, out):
        out.push('EXIT;')


class Empty(Stmt):
    fields = [
    ]

    def generate(self, out):
        out.push(';')


class Assign(Stmt):
    fields = [
        ('lval', Expr),
        ('rval', Expr),
    ]

    def generate(self, out):
        out.push(self.lval)
        out.push(' := ')
        out.push(self.rval)
        out.push(';')


class ExprStmt(Stmt):
    fields = [
        ('expr', Expr),
    ]

    def generate(self, out):
        out.push(self.expr)
        out.push(';')


# -- POUs ---------------------------------------------------------------------

class POU(Node):
    pass


class Globals(POU):
    fields = [
        ('vars', VarBlock),
    ]

    def generate(self, out):
        out.push_line(self.vars)


class Struct(POU):
    fields = [
        ('name', str),
        ('vars', VarBlock),
    ]

    def generate(self, out):
        out.push_line('TYPE ')
        out.push(self.name)
        out.push(' :')
        out.push_line(self.vars)
        out.push_line('END_TYPE')


class Program(POU):
    fields = [
        ('name', str),
        ('vars', VarBlock),
        ('body', [Stmt]),
    ]

    def generate(self, out):
        out.push_line('PROGRAM ')
        out.push(self.name)
        out.push_line(self.vars)
        for stmt in self.body:
            out.push_line(stmt)
        out.push_line('END_PROGRAM')


class FunctionBlock(POU):
    fields = [
        ('name', str),
        ('vars', VarBlock),
        ('ivars', VarBlock),
        ('ovars', VarBlock),
        ('iovars', VarBlock),
        ('body', [Stmt]),
    ]

    def generate(self, out):
        out.push_line('FUNCTION_BLOCK ')
        out.push(self.name)
        out.push_line(self.vars)
        out.push_line(self.ivars)
        out.push_line(self.ovars)
        out.push_line(self.iovars)
        for stmt in self.body:
            out.push_line(stmt)
        out.push_line('END_FUNCTION_BLOCK')


class Project(Node):
    fields = [
        ('pous', [POU]),
    ]
