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

"""Output writer."""

from . import st_ast as st


class Output:

    def __init__(self, stream):
        self.indent = 0
        self.w = stream

    def push(self, item):
        if isinstance(item, str):
            self.w.write(item)
        elif isinstance(item, st.Node):
            item.generate(self)

    def push_sep(self, sep, items):
        for i, item in enumerate(items):
            self.push(item)
            if i != len(items) - 1:
                self.push(sep)

    def push_line(self, item):
        self.w.write('\n' + ' ' * self.indent)
        self.push(item)

    def more_indent(self):
        self.indent += 4

    def less_indent(self):
        self.indent -= 4
