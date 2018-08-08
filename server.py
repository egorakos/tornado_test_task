#!/usr/bin/python

import logging
from tornado.ioloop import IOLoop
from tornado import gen
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.options import options, define
from functools import reduce
from time import time as timestamp

define("client_port", default=8888, help="TCP port for clients")
define("viewer_port", default=8889, help="TCP port for viewers")
logger = logging.getLogger(__name__)


class ClientsServer(TCPServer):
    clients = {}
    messages = []

    @gen.coroutine
    def handle_stream(self, stream, address):
        logger.info("Connected client %s", address)
        ClientsServer.clients[address] = None
        while True:
            try:
                data = yield stream.read_until(b"\r\n")
                if int.from_bytes(data[:1], byteorder='big', signed=False):
                    raise Exception('wrong header')
                message_num = int.from_bytes(
                    data[1:3], byteorder='big', signed=False
                    )
                client_id = data[3:11].decode('ascii')
                state = int.from_bytes(
                    data[11:12],
                    byteorder='big', signed=False
                    )
                numfields = int.from_bytes(
                    data[12:13], byteorder='big', signed=False
                    )
                zxor1 = int.from_bytes(
                    data[-3:-2], byteorder='big', signed=False
                    )
                zxor2 = reduce(lambda x, y: x ^ y, data[:-3])
                ClientsServer.clients[address] = (
                    client_id,
                    message_num,
                    state,
                    int(timestamp())
                    )
                logger.info(
                    "Recived message# %d from '%s' with %d fields:",
                    message_num,
                    client_id,
                    numfields
                    )
                logger.info("checksums are %s and %s ", hex(zxor1), hex(zxor2))
                if zxor1 != zxor2:
                    raise Exception('checksum does not match')
                pos = 13
                viewer_msg = ''
                for n in range(numfields):
                    fieldname = data[pos:pos+8].decode('ascii')
                    fieldval = int.from_bytes(
                        data[pos+8:pos+12], byteorder='big', signed=False
                        )
                    pos += 12
                    logger.info("%s : %d ", fieldname, fieldval)
                    viewer_msg += '[' + str(client_id) + ']'
                    viewer_msg += fieldname + '|' + str(fieldval) + '\r\n'
                ClientsServer.messages.append(viewer_msg)

                client_msg = b"\x11" + data[1:3]
                client_msg += reduce(lambda x, y: x ^ y, client_msg).to_bytes(
                    1, byteorder='big', signed=False
                    )
                client_msg += b"\r\n"
                yield stream.write(client_msg)
            except StreamClosedError:
                logger.warning("Client %s left", address)
                ClientsServer.clients.pop(address)
                break
            except Exception as e:
                logger.warning(e)
                # формируем сообщение клиенту при ошибке
                errmsg = bytes('', encoding='utf-8') + b'\x12'
                try:
                    errmsg += data[1:3]
                except:
                    errmsg += b'\x00\x00'
                zxor = reduce(lambda x, y: x ^ y, errmsg)
                errmsg += zxor.to_bytes(1, byteorder='big', signed=False)
                errmsg += b'\r\n'
                yield stream.write(errmsg)


class ViewServer(TCPServer):
    streams = set()

    @gen.coroutine
    def handle_stream(self, stream, address):
        ViewServer.streams.add(stream)
        logger.info("Connected viewer %s", address)
        clients = ''
        for a in ClientsServer.clients.keys():
            c = ClientsServer.clients[a]
            clients += "[" + str(c[0]) + "]" + str(c[1]) + "|"
            if c[2] == 1:
                clients += 'IDLE'
            elif c[2] == 2:
                clients += 'ACTIVE'
            elif c[2] == 3:
                clients += 'RECHARGE'
            clients += "|" + str(int(timestamp())-c[3]) + "\r\n"
        clients += '\n'
        yield stream.write(bytearray(clients, 'utf-8'))


    @gen.coroutine
    def get_messages(self):
        while True:
            try:
                if ClientsServer.messages:
                    while ClientsServer.messages:
                        m = server.messages.pop(0)
                        for s in ViewServer.streams:
                            try:
                                s.write(bytearray(str(m)+"\r\n", 'utf-8'))
                            except StreamClosedError:
                                ViewServer.streams.remove(s)
                                logger.warning("Viewer left")
            except Exception as e:
                logger.warning(e)
            yield gen.Task(IOLoop.current().add_timeout, timestamp()+1)

if __name__ == "__main__":
    options.parse_command_line()
    server = ClientsServer()
    server.listen(options.client_port)
    server.start()
    logger.info("Listening clients on TCP port %d", options.client_port)
    view_server = ViewServer()
    view_server.listen(options.viewer_port)
    view_server.start()
    logger.info("Listening viewers on TCP port %d", options.viewer_port)
    IOLoop.current().add_callback(lambda: view_server.get_messages())
    IOLoop.current().start()
