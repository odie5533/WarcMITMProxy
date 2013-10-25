# Copyright (C) David Bern
# See COPYRIGHT.md for details


from libmproxy import controller, proxy
from netlib import http_status
import argparse
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
        if filename is None:
            filename = "out.warc.gz"
            print "WarcOutput was not given a filename. Using", filename
        self.use_gzip = True if args.file.endswith('.gz') else False
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

class WarcMaster(controller.Master):
    def __init__(self, filename, server):
        WarcOutputSingleton(filename)
        controller.Master.__init__(self, server)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    def handle_request(self, msg):
        url = constructUrl(msg)
        version = http_version(msg.httpversion)
        headline = ' '.join([msg.method, url, 'HTTP/'+version])
        block = headline + '\r\n' + str(msg.headers) + '\r\n' + str(msg.content)
        record = warcrecords.WarcRequestRecord(url=url, block=block)
        WarcOutputSingleton().write_record(record)
        
        msg.reply()

    def handle_response(self, msg):
        version = http_version(msg.httpversion)
        h_status = 'HTTP/'+version+' '+str(msg.code)+' '+http_status.RESPONSES[msg.code]
        block = h_status + '\r\n' + str(msg.headers) + '\r\n' +msg.content
        url = constructUrl(msg.request)
        record = warcrecords.WarcResponseRecord(url=url, block=block)
        WarcOutputSingleton().write_record(record)
        
        msg.reply()

parser = argparse.ArgumentParser(description='Warc Man-in-the-Middle Proxy')
parser.add_argument('--pem', default='ca.pem',
                    help='Privacy-enhanced Electronic Mail file.')
parser.add_argument('-p', '--port', default=8000,
                    help='Port to run the proxy server on.')
parser.add_argument('-f', '--file', default='out.warc.gz',
                    help='WARC filename to save to. Include .gz for gzip.')

args = parser.parse_args()
args.pem = os.path.expanduser(args.pem)
if not os.path.isfile(args.pem):
    print "Supplied pem file can not be found:", args.pem
    exit()
try: # Parse the port into an integer
    args.port = int(args.port)
except:
    print "Please specify a valid number for the port:", args.port
    exit()

# Create proxy config from PEM file
config = proxy.ProxyConfig(
    cacert = os.path.expanduser(args.pem)
)
server = proxy.ProxyServer(config, args.port)
m = WarcMaster(args.file, server)
print "Proxy server running on port", args.port
m.run()
