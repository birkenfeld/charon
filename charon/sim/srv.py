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

from struct import pack, unpack, unpack_from
import socketserver


class ModbusExc(Exception):
    pass


class ConnectionHandler(socketserver.BaseRequestHandler):

    def handle(self):
        sock = self.request
        while True:
            # read request
            req = sock.recv(8)
            if len(req) != 8:
                return
            tidpid, lgth, unit, func = unpack('>IHBB', req)
            data = sock.recv(lgth - 2)
            try:
                resp = self.handle_req(lgth, func, data)
            except ModbusExc as e:
                msg = pack('>IHBBB', tidpid, lgth, unit, func | 0x80,
                           e.args[0])
            except Exception:
                msg = pack('>IHBBB', tidpid, lgth, unit, func | 0x80, 1)
            else:
                msg = pack('>IHBB', tidpid, 2 + len(resp), unit, func) + resp
            sock.sendall(msg)

    def handle_req(self, lgth, func, data):
        # decode request
        if len(data) != lgth - 2:      # illegal data value
            raise ModbusExc(3)
        if func not in (3, 4, 6, 16):  # illegal function
            raise ModbusExc(1)
        addr, = unpack_from('>H', data)
        addr = addr - 0x3000  # map from Beckhoff standard
        if addr >= 0x1000:
            # illegal data address
            raise ModbusExc(2)
        baddr = 2*addr + 0x10000  # map to byte address
        with self.server.cond:
            self.server.cond.wait()  # wait for go ahead for one round
            if func in (3, 4):
                # read data
                nreg, = unpack('>H', data[2:])
                read = self.server.plc.read(baddr, 2*nreg)
                return pack('>B', 2*nreg) + \
                    b''.join(pack('>H', *unpack('H', read[2*i:2*i+2]))
                             for i in range(nreg))
            elif func == 6:
                wdata = pack('H', *unpack('>H', data[2:4]))
                self.server.plc.write(baddr, wdata)
                return data
            elif func == 16:
                nreg, dbytes = unpack_from('>HB', data[2:])
                assert dbytes == 2*nreg
                wdata = b''.join(pack('H', *unpack('>H', data[2*i+5:2*i+7]))
                                 for i in range(nreg))
                self.server.plc.write(baddr, wdata)
                return data[:4]


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, plc, cond):
        self.plc = plc
        self.cond = cond
        socketserver.ThreadingTCPServer.__init__(self, ('localhost', 5002),
                                                 ConnectionHandler)
