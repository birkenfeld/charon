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

"""Python -> ST translator."""

import os
import ast
import sys

from .visit import AstVisitor
from .out import Output


class FatalError(Exception):
    pass


class Source:

    @staticmethod
    def new(path):
        if os.path.isfile(path):
            return FileSource(path)
        elif os.path.isdir(path):
            return DirectorySource(path)
        raise FatalError('source not found: %r' % path)

    def get_units(self):
        raise NotImplementedError


class FileSource(Source):

    def __init__(self, path):
        self.path = path

    def get_units(self):
        return [
            Unit(os.path.basename(self.path), open(self.path).read())
        ]


class DirectorySource(Source):
    pass


class Unit:

    ast = None
    generated = None

    def __init__(self, name, code):
        self.name = name
        self.code = code


class Translator:

    def __init__(self, source):
        self.source = source
        self.units = []

    def run(self):
        success = True
        for unit in self.source.get_units():
            if self.parse(unit):
                if self.translate_ast(unit):
                    if self.generate(unit):
                        self.units.append(unit)
                        continue
            success = False
        success &= self.finish()
        success &= self.emit()
        return success

    def parse(self, unit):
        try:
            unit.ast = ast.parse(unit.code, unit.name)
        except SyntaxError as e:
            # XXX: report properly
            raise FatalError('code is not well-formed Python: %s' % e)
        else:
            return True

    def translate_ast(self, unit):
        checker = AstVisitor(self)
        unit.project = checker.visit(unit.ast)
        unit.project.fixup_parents()
        return not checker.failed

    def generate(self, unit):
        for pou in unit.project.pous:
            out = Output(sys.stdout)
            pou.generate(out)
            out.push('\n\n')
        return True

    def finish(self):
        return True

    def emit(self):
        return True
