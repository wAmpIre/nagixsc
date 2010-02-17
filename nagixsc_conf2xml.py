#!/usr/bin/python

import optparse
import sys
import urllib2

##############################################################################

from nagixsc import *

##############################################################################

parser = optparse.OptionParser()

parser.add_option('-c', '', dest='conffile', help='Config file')
parser.add_option('-o', '', dest='outfile', help='Output file name, "-" for STDOUT or HTTP POST URL')
parser.add_option('-e', '', dest='encoding', help='Encoding ("%s")' % '", "'.join(available_encodings()) )
parser.add_option('-H', '', dest='host', help='Hostname/section to search for in config file')
parser.add_option('-D', '', dest='service', help='Service description to search for in config file (needs -H)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name, if outfile is HTTP(S) URL')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password, if outfile is HTTP(S) URL')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(conffile='nagixsc.conf')
parser.set_defaults(outfile='-')
parser.set_defaults(encoding='base64')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

if not check_encoding(options.encoding):
	print 'Wrong encoding method "%s"!' % options.encoding
	print 'Could be one of: "%s"' % '", "'.join(available_encodings())
	sys.exit(127)

##############################################################################

config = read_inifile(options.conffile)

if not config:
	print 'Config file "%s" could not be read!' % options.conffile
	sys.exit(5)

checks = conf2dict(config, options.host, options.service)

xmldoc = xml_from_dict(checks, options.encoding)

if options.outfile.startswith('http'):
	(headers, body) = encode_multipart(xmldoc, options.httpuser, options.httppasswd)

	try:
		response = urllib2.urlopen(urllib2.Request(options.outfile, body, headers)).read()
	except urllib2.HTTPError, error:
		print error
		sys.exit(6)
	except urllib2.URLError, error:
		print error.reason[1]
		sys.exit(7)

	print response

elif options.outfile == '-':
	xmldoc.saveFormatFile('-', format=1)

else:
	xmldoc.saveFile(options.outfile)

