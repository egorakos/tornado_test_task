#!/usr/bin/python

from tornado.ioloop import IOLoop
from tornado import gen
from tornado.tcpclient import TCPClient
from tornado.options import options, define

define("host", default="localhost", help="TCP server host")
define("port", default=8889, help="TCP port to connect to")

@gen.coroutine
def get_message():
    stream = yield TCPClient().connect(options.host, options.port)
    while True:
        resp = yield stream.read_until(b"\r\n")
        print(resp.decode('utf-8')[:-2])


if __name__ == "__main__":
    options.parse_command_line()
    while True:
        IOLoop.current().run_sync(get_message)

