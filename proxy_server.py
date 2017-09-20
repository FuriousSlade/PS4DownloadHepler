#!/usr/bin/env python
# -*- coding: utf-8 -*-
import gevent.monkey; gevent.monkey.patch_all()
from gevent.server import StreamServer
from gevent import socket
from gevent import select
import gevent
import StringIO
import re
import os
import logging

BUFFER_SIZE = 8192

logging.basicConfig(level=logging.INFO)


class DownloadHook(file):

    def __init__(self, name):
        super(DownloadHook, self).__init__(name)
        self.data = ''

    def sendall(self, data):
        self.data += data

    def recv(self, buffer):
        head_list = self.data.split('\r\n\r\n')[0].split('\r\n')
        request_range = None
        for i in head_list:
            if i.split(' ')[0] == 'Range:':
                request_range = i.split(' ')[1]
                break
        if request_range is None:
            start, end = 0, 65536
        else:
            start, end = request_range.split('=')[1].split('-')
        pkg_size = os.path.getsize('{}'.format(self.name))
        self.seek(int(start))
        data = 'HTTP/1.1 206 Partial Content\r\n'
        data += 'Accept-Ranges: bytes\r\n'
        data += 'Content-Type: application/octet-stream\r\n'
        data += 'Content-Range: bytes {}-{}/{}\r\n'.format(start, end, pkg_size)
        data += 'Content-Length: {}\r\n\r\n'.format(int(end) - int(start) + 1)
        data += self.read(int(end) - int(start) + 1)
        return data


class Forward(object):

    def __init__(self, sock):
        self.s = None
        self.data = None
        self.header_info = None
        self.side = None
        self.time = 0
        self.inputs = [sock]
        self.channel = {}
        self.content_length = None
        self.recv_length = 0
        self.pkg_name = ''

    def get_header_info(self):
        header = self.data.split('\r\n\r\n')[0]
        method = header.split('\r\n')[0].split(' ')[0]
        uri = header.split('\r\n')[0].split(' ')[1]
        m = re.search(r'Host: (.*?)\r\n', header)
        host = m.groups()[0]
        port = 80
        if len(host.split(':')) > 1:
            host, port = host.split(':')[0], int(host.split(':')[1])
        self.header_info = {
            "method": method,
            "host": host,
            "port": port,
            "uri": uri
        }

    def get_other_side(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.connect((self.header_info['host'], self.header_info['port']))
        self.side = s

    def is_download_pkg(self):
        if self.header_info['host'] == 'gs2.ww.prod.dl.playstation.net':
            self.pkg_name = self.header_info['uri'].split('/')[-1].split('?')[0]
            if self.pkg_name.endswith('.pkg') is True:
                return True
        return False

    def get_content_length(self):
        head_list = self.data.split('\r\n\r\n')[0].split('\r\n')
        for i in head_list:
            if i.split(' ')[0] == 'Content-Length:':
                self.content_length = int(i.split(' ')[1])

    def do_work(self):
        while self.time >= 0:
            inputready, _, _ = select.select(self.inputs, [], [])
            for self.s in inputready:
                if self.s.__class__.__name__ == 'socket':
                    self.data = self.s.recv(BUFFER_SIZE)
                    if self.time == 0:
                        self.get_header_info()
                        if self.is_download_pkg():
                            logging.info('Download url: ', self.header_info['uri'])
                            f = DownloadHook('download/{}'.format(self.pkg_name))
                            self.inputs.append(f)
                            self.channel = {
                                self.s: f,
                                f: self.s
                            }
                        else:
                            self.get_other_side()
                            self.inputs.append(self.side)
                            self.channel = {
                                self.s: self.side,
                                self.side: self.s
                            }
                            if self.header_info['method'] == 'CONNECT':
                                self.s.send('HTTP/1.0 200 Connection Established\r\n\r\n')
                                break
                    elif self.s == self.side:
                        if self.data.startswith('HTTP'):
                            self.get_content_length()
                            self.recv_length = len(self.data.split('\r\n\r\n')[1])
                        else:
                            self.recv_length += len(self.data)
                    if len(self.data) == 0:
                        self.on_close()
                        break
                    else:
                        self.on_recv()
                        if self.content_length == self.recv_length:
                            self.on_close()
                elif self.s.__class__.__name__ == 'DownloadHook':
                    self.data = self.s.recv(BUFFER_SIZE)
                    self.on_recv()
                    self.on_close()
                    self.time = -2
                    break
            self.time += 1

    def on_recv(self):
        data = self.data
        self.channel[self.s].sendall(data)

    def on_close(self):
        self.inputs.remove(self.s)
        self.inputs.remove(self.channel[self.s])
        out = self.channel[self.s]
        self.channel[out].close()
        self.channel[self.s].close()
        del self.channel[out]
        del self.channel[self.s]


def handle(sock, address):
    logging.info('New connection from %s:%s' % address)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    forwarder = Forward(sock)
    gevent.spawn(forwarder.do_work)


def main():
    ip = '0.0.0.0'
    port = 8888
    server = StreamServer((ip, port), handle)
    logging.info('Starting proxy server on {} port {}'.format(ip, port))
    server.serve_forever()

if __name__ == '__main__':
    main()