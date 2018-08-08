#!/usr/bin/python3

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


def message_pharser(data):
    datadict = {}
    if int.from_bytes(data[:1], byteorder='big', signed=False):
        datadict['firstbyte'] = True
    datadict['message_num'] = int.from_bytes(
        data[1:3], byteorder='big', signed=False
        )
    datadict['client_id'] = data[3:11].decode('ascii')
    datadict['state'] = int.from_bytes(
        data[11:12],
        byteorder='big', signed=False
        )
    datadict['numfields'] = int.from_bytes(
        data[12:13], byteorder='big', signed=False
        )
    datadict['zxor1'] = int.from_bytes(
        data[-3:-2], byteorder='big', signed=False
        )
    datadict['zxor2'] = reduce(lambda x, y: x ^ y, data[:-3])
    pos = 13
    datadict['fields'] = []
    for n in range(datadict['numfields']):
        fieldname = data[pos:pos+8].decode('ascii')
        fieldval = int.from_bytes(
            data[pos+8:pos+12], byteorder='big', signed=False
            )
        pos += 12
        datadict['fields'].append((fieldname, fieldval))
    return(datadict)


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
                dd = message_pharser(data)
                if 'firstbyte' in dd.keys():
                   raise Exception('wrong header')
                else:
                    if dd['zxor1'] != dd['zxor2']:
                        raise Exception('checksum does not match')
                    else:
                        logger.info(
                            "Recived message# %d from '%s' with %d fields:",
                            dd['message_num'],
                            dd['client_id'],
                            dd['numfields']
                            )
                        logger.info(
                            "xors are %s and %s, all right",
                            hex(dd['zxor1']),
                            hex(dd['zxor2'])
                            )
                    ClientsServer.clients[address] = (
                        dd['client_id'],
                        dd['message_num'],
                        dd['state'],
                        int(timestamp()),
                        )
                    viewer_msg = ''
                    for field in dd['fields']:
                        viewer_msg += '[{}]{}|{}\r\n'.format(
                            str(dd['client_id']),
                            str(field[0]),
                            str(field[1])
                            )
                        logger.info("%s : %d ", field[0], field[1])
                    ClientsServer.messages.append(viewer_msg)
                    # формируем сообщение клиенту
                    client_msg = b"\x11" + dd['message_num'].to_bytes(
                        1, byteorder='big', signed=False
                        )
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
            if c[2] == 1:
                status = 'IDLE'
            elif c[2] == 2:
                status = 'ACTIVE'
            elif c[2] == 3:
                status= 'RECHARGE'
            clients += "[{}]{}|{}|{} \r\n".format(
                 str(c[0]),
                 str(c[1]),
                 status,
                 str(int(timestamp())-c[3])
                 )
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
