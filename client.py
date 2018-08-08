#!/usr/bin/python

from tornado.ioloop import IOLoop
from tornado import gen
from tornado.tcpclient import TCPClient
from tornado.options import options, define
import random
from time import sleep
from os import getpid


define("host", default="localhost", help="TCP server host")
define("port", default=8888, help="TCP port to connect to")
define("id", default='id' + str(getpid()), help="Client id")
define("interval", default=4, help="interval between messages")
define("state", default=2, help="client state")
define("minfields", default=1, help="min numfields")
define("maxfields", default=16, help="max numfields")


def randomfields(a, b):
    """ generate dict with random items """
    fields = {}
    for i in range(random.randint(options.minfields, options.maxfields)):
        fields['field' + str(i)] = random.randint(0, 256)
    return fields


def genmessage(n, a, b):
    request = bytes('', encoding='utf-8')
    a = 0
    # первый байт 0
    request += a.to_bytes(1, byteorder='big', signed=False)
    # два байта с номером сообщения
    request += n.to_bytes(2, byteorder='big', signed=False)
    # идентификатор клиента
    client_id = options.id[:8].ljust(8, " ").encode()
    request += client_id
    # статус клиента
    state = options.state if options.state in (1, 2, 3) else 3
    request += state.to_bytes(1, byteorder='big', signed=False)
    # request += (options.id+'\n').encode()
    # numfields по количеству элементов словаря
    fields = randomfields(a, b)
    numfields = len(fields)
    request += numfields.to_bytes(1, byteorder='big', signed=False)
    # поля из словаря
    for item in fields:
        request += item[:8].ljust(8, " ").encode('ascii')
        request += fields[item].to_bytes(4, byteorder='big', signed=False)
    # xor от сообщения
    checksum = 0
    for b in request:
        # print(hex(b))
        checksum ^= b
    log = 'Generated message with ' + str(numfields)
    log += ' fields. xor is ' + hex(checksum)
    print(log)
    # print(checksum.to_bytes(1,byteorder='big',signed=False))
    request += checksum.to_bytes(1, byteorder='big', signed=False)
    return request


@gen.coroutine
def send_message():
    stream = yield TCPClient().connect(options.host, options.port)
    n = 1
    while True:
        request = genmessage(n, 0, 16)
        request += (b'\r\n')
        yield stream.write(request)
        print("Sent    : ", request)
        reply = yield stream.read_until(b"\r\n")
        print("Response: ", reply)
        n += 1
        sleep(options.interval)


if __name__ == "__main__":
    options.parse_command_line()
    while True:
        IOLoop.current().run_sync(send_message)
        sleep(options.interval)
