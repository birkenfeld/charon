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

"""Python AST visitor."""

import ast

from . import st_ast as st


class AstVisitor(ast.NodeVisitor):

    def __init__(self, trans):
        self.failed = False
        self.trans = trans

    def bail(self, node, why):
        # XXX: proper error handling
        if hasattr(node, 'lineno'):
            raise SyntaxError('line %d, col %d: %s' %
                              (node.lineno, node.col_offset, why))
        else:
            raise SyntaxError(why)

    def visit_all(self, nodes):
        return [v for v in [self.visit(n) for n in nodes] if v]

    # -- visitors -------------------------------------------------------------

    binop_tbl = {
        ast.Add: '+',
        ast.Sub: '-',
        ast.Mult: '*',
        ast.Div: None,
        ast.FloorDiv: '/',
        ast.Mod: 'MOD',
        ast.Pow: '**',
        ast.BitOr: 'OR',
        ast.BitXor: 'XOR',
        ast.BitAnd: 'AND',
    }
    if hasattr(ast, 'MatMult'):
        binop_tbl[ast.MatMult] = None
    binop_func_tbl = {
        ast.LShift: 'SHL',
        ast.RShift: 'SHR',
    }
    unop_tbl = {
        ast.Invert: 'NOT',
        ast.Not: 'NOT',
        ast.UAdd: '',
        ast.USub: '-',
    }
    cmpop_tbl = {
        ast.Eq: '=',
        ast.NotEq: '<>',
        ast.Lt: '<',
        ast.LtE: '<=',
        ast.Gt: '>',
        ast.GtE: '>=',
        ast.Is: None,
        ast.IsNot: None,
        ast.In: None,
        ast.NotIn: None,
    }

    def visit_Module(self, node):
        return st.Project(pous=self.visit_all(node.body))

    def visit_ImportFrom(self, node):
        # print(ast.dump(node))
        # XXX determine needed libraries
        return

    def visit_ClassDef(self, node):
        if len(node.bases) != 1 or not isinstance(node.bases[0], ast.Name):
            self.bail(node, 'classes must inherit Struct, Enum or Globals')
        if node.keywords:
            self.bail(node, 'classes cannot have keywords')
        if node.decorator_list:
            self.bail(node, 'classes cannot have decorators')
        # XXX transform var assigns
        vars = []
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or \
               len(stmt.targets) != 1 or \
               not isinstance(stmt.targets[0], ast.Name):
                self.bail(node, 'only Var assignments allowed in structs')
            var = self.get_var(stmt.targets[0].id, stmt.value)
            vars.append(var)
        if node.bases[0].id == 'Struct':
            return st.Struct(name=node.name, vars=st.VarBlock(type='STRUCT',
                                                              vars=vars))
        elif node.bases[0].id == 'Enum':
            self.bail(node, 'enums are not supported yet')  # XXX
        elif node.bases[0].id == 'Globals':
            return st.Globals(vars=st.VarBlock(type='VAR_GLOBAL', vars=vars))

    def get_var(self, name, node):
        if not isinstance(node, ast.Call) or \
           not isinstance(node.func, ast.Name) or \
           node.func.id != 'Var':
            self.bail(node, 'must be a Var declaration')
        if len(node.args) < 1:
            self.bail(node, 'Var must have a type')
        vartype = self.get_var_type(node.args[0])
        default = []
        if len(node.args) >= 2:
            default = [self.visit(node.args[1])]
        loc = []
        if len(node.keywords) == 1 and \
           node.keywords[0].arg == 'at' and \
           isinstance(node.keywords[0].value, ast.Str):
            loc = [node.keywords[0].value.s]
        return st.Var(name=name, type=vartype, default=default, loc=loc)

    def get_var_type(self, node):
        if isinstance(node, ast.Name):
            typename = node.id.upper() if node.id.islower() else node.id
            return st.SimpleType(id=typename)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                self.bail('strange type: %s' % node)
            # XXX: check conditions
            if node.func.id == 'string':
                return st.StringType(length=node.args[0].n)
            elif node.func.id == 'array':
                inner = self.get_var_type(node.args[0])
                return st.ArrayType(imin=node.args[1].n,
                                    imax=node.args[2].n,
                                    inner=inner)

    def visit_FunctionDef(self, node):
        if len(node.decorator_list) != 1 or \
           not isinstance(node.decorator_list[0], ast.Call):
            self.bail(node, 'function needs a decorator to select type')
        # XXX: check deco
        deco = node.decorator_list[0]
        if deco.func.id == 'program':
            vars = []
            for kw in deco.keywords:
                vars.append(self.get_var(kw.arg, kw.value))
            vars = st.VarBlock(type='VAR', vars=vars)
            stmts = self.visit_all(node.body)
            return st.Program(name=node.name, vars=vars, body=stmts)
        self.bail(node, 'unsupported decorator: %s' % deco.func.id)

    def visit_If(self, node):
        # XXX: recognize switch/case
        expr = self.visit(node.test)
        thens = self.visit_all(node.body)
        elses = self.visit_all(node.orelse)
        return st.If(expr=expr, thens=thens, elses=elses)

    def visit_While(self, node):
        if node.orelse:
            self.bail(node, 'else on while loops not allowed')
        expr = self.visit(node.test)
        stmts = self.visit_all(node.body)
        return st.While(expr=expr, stmts=stmts)

    def visit_Break(self, node):
        return st.Exit()

    def visit_AugAssign(self, node):
        lval = self.visit(node.target)
        rval = self.visit(node.value)
        for (opcls, op) in self.binop_tbl.items():
            if isinstance(node.op, opcls):
                if op is None:
                    self.bail(node, 'operator %s is not supported' % node.op)
                return st.Assign(lval=lval, rval=st.BinOp(left=lval,
                                                          right=rval, op=op))
        for (opcls, op) in self.binop_func_tbl.items():
            if isinstance(node.op, opcls):
                return st.Assign(lval=lval, rval=st.Call(base=st.Id(id=op),
                                                         args=[lval, rval]))
        self.bail(node, 'unhandled binop?')

    def visit_Assign(self, node):
        # XXX: special case for globals assignment
        if isinstance(node.targets[0], ast.Name) and \
           node.targets[0].id == 'g':
            return None
        if len(node.targets) > 1:
            self.bail(node, 'only one assign target supported')
        lval = self.visit(node.targets[0])
        rval = self.visit(node.value)
        return st.Assign(lval=lval, rval=rval)

    def visit_Pass(self, node):
        return st.Empty()

    def visit_Expr(self, node):
        return st.ExprStmt(expr=self.visit(node.value))

    def visit_Call(self, node):
        base = self.visit(node.func)
        if node.keywords:
            if node.args:
                self.bail(node, 'function call must have either only args or '
                          'only keyword args (initializer)')
            kwds = [st.KwArg(name=kw.arg, value=self.visit(kw.value))
                    for kw in node.keywords]
            return st.StructInitializer(items=kwds)
        if isinstance(base, st.Id):
            base.id = base.id.upper()
        args = self.visit_all(node.args)
        return st.Call(base=base, args=args)

    def visit_UnaryOp(self, node):
        expr = self.visit(node.operand)
        for (opcls, op) in self.unop_tbl.items():
            if isinstance(node.op, opcls):
                return st.UnOp(expr=expr, op=op)
        self.bail(node, 'unhandled unop?')

    def visit_BoolOp(self, node):
        if len(node.values) > 2:
            self.bail('bool ops with > 2 elements not supported')
        op = 'AND' if isinstance(node.op, ast.And) else 'OR'
        left = self.visit(node.values[0])
        right = self.visit(node.values[1])
        return st.BinOp(left=left, right=right, op=op)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        for (opcls, op) in self.binop_tbl.items():
            if isinstance(node.op, opcls):
                if op is None:
                    self.bail(node, 'operator %s is not supported' % node.op)
                return st.BinOp(left=left, right=right, op=op)
        for (opcls, op) in self.binop_func_tbl.items():
            if isinstance(node.op, opcls):
                return st.Call(base=st.Id(id=op), args=[left, right])
        self.bail(node, 'unhandled binop?')

    def visit_Compare(self, node):
        # XXX handle chained comps
        left = self.visit(node.left)
        if len(node.comparators) > 1:
            self.bail(node, 'chained comparisons not supported')
        right = self.visit(node.comparators[0])
        for (opcls, op) in self.cmpop_tbl.items():
            if isinstance(node.ops[0], opcls):
                if op is None:
                    self.bail(node, 'operator %s is not supported' %
                              node.ops[0])
                return st.BinOp(left=left, right=right, op=op)
        self.bail(node, 'unhandled cmpop?')

    def visit_List(self, node):
        exprs = self.visit_all(node.elts)
        return st.List(exprs=exprs)

    def visit_Attribute(self, node):
        expr = self.visit(node.value)
        # XXX: special casing!
        if isinstance(expr, st.Id) and expr.id in ('g', 'v'):
            return st.Id(id=node.attr)
        return st.Member(base=expr, member=st.Id(id=node.attr))

    def visit_Subscript(self, node):
        expr = self.visit(node.value)
        if not isinstance(node.slice, ast.Index):
            self.bail(node, 'slicing is not supported')
        idx = node.slice.value
        if isinstance(idx, ast.List):
            if len(idx.elts) != 1 or \
               not isinstance(idx.elts[0], ast.Num):
                self.bail(node, 'bit index must have one numeric element')
            return st.Member(base=expr, member=st.Id(id=str(idx.elts[0].n)))
        index = self.visit(idx)
        return st.Subscript(base=expr, sub=index)

    def visit_Name(self, node):
        return st.Id(id=node.id)

    def visit_Num(self, node):
        if isinstance(node.n, float):
            return st.Float(f=node.n)
        else:
            return st.Int(i=node.n)

    def visit_Str(self, node):
        return st.Str(s=node.s)

    def visit_NameConstant(self, node):
        if node.value is True:
            return st.Id(id='TRUE')
        elif node.value is False:
            return st.Id(id='FALSE')
        else:
            self.bail(node, 'constant %s not supported' % node.value)

    def visit(self, node):
        visitor = getattr(self, 'visit_' + node.__class__.__name__,
                          self.visit_unknown)
        return visitor(node)

    def visit_unknown(self, node):
        self.bail(node, 'construct %s is not allowed' %
                  node.__class__.__name__)
