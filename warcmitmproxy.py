# Copyright (C) David Bern
# See LICENSE.md for details


from libmproxy import controller, proxy
from netlib import http_status
import os
import urlparse
import warcrecords

"""
Singleton that handles maintaining a single output file for many connections

"""
class WarcOutputSingleton(object):
    _instance = None

    def __new__(cls, * args, **kwargs):
        if not cls._instance:
            cls._instance = super(WarcOutputSingleton, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, filename=None):
        self.use_gzip = False
        self.filename = "out.warc.gz"
        if filename is not None:
            self.filename = filename

        # Make sure init is not called more than once
        try:
            self.__fo
        except AttributeError:
            self.__fo = open(self.filename, 'wb')
            record = warcrecords.WarcinfoRecord()
            record.write_to(self.__fo, gzip=self.use_gzip)

    # Write a given record to the output file
    def write_record(self, record):
        record.write_to(self.__fo, gzip=self.use_gzip)

def constructUrl(msg):
    port = ':'+str(msg.port) if msg.port and msg.port != 80 and msg.port != 443 else ''
    return urlparse.urlunsplit([msg.scheme, msg.host+port, msg.path, '', ''])
def http_version(httpversion):
    return str(httpversion[0]) + '.' + str(httpversion[1])

class StickyMaster(controller.Master):
    def __init__(self, server):
        controller.Master.__init__(self, server)
        self.stickyhosts = {}

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    def handle_request(self, msg):
        hid = (msg.host, msg.port)
        url = constructUrl(msg)
        version = http_version(msg.httpversion)
        headline = ' '.join([msg.method, url, 'HTTP/'+version])
        block = headline + '\r\n' + str(msg.headers) + '\r\n' + str(msg.content)
        record = warcrecords.WarcRequestRecord(url=url, block=block)
        WarcOutputSingleton().write_record(record)
        
        msg.reply()

    def handle_response(self, msg):
        hid = (msg.request.host, msg.request.port)
        version = http_version(msg.httpversion)
        h_status = 'HTTP/'+version+' '+str(msg.code)+' '+http_status.RESPONSES[msg.code]
        block = h_status + '\r\n' + str(msg.headers) + '\r\n' +msg.content
        url = constructUrl(msg.request)
        record = warcrecords.WarcResponseRecord(url=url,
                                                block=block)
        WarcOutputSingleton().write_record(record)
        
        msg.reply()


config = proxy.ProxyConfig(
    cacert = os.path.expanduser("ca.pem")
)
server = proxy.ProxyServer(config, 8000)
m = StickyMaster(server)
m.run()
