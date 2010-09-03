#!/usr/bin/python

import optparse
import sys

##############################################################################

from nagixsc import *

##############################################################################

parser = optparse.OptionParser()

parser.add_option('-s', '', dest='socket', help='Livestatus socket to connect')
parser.add_option('-o', '', dest='outfile', help='Output file name, "-" for STDOUT or HTTP POST URL')
parser.add_option('-e', '', dest='encoding', help='Encoding ("%s")' % '", "'.join(available_encodings()) )
parser.add_option('-H', '', dest='host', help='Hostname/section to search for in config file')
parser.add_option('-D', '', dest='service', help='Service description to search for in config file (needs -H)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name, if outfile is HTTP(S) URL')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password, if outfile is HTTP(S) URL')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(socket=None)
parser.set_defaults(outfile='-')
parser.set_defaults(encoding='base64')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

if not options.socket:
	print 'No socket specified!\n'
	parser.print_help()
	sys.exit(1)

if not check_encoding(options.encoding):
	print 'Wrong encoding method "%s"!' % options.encoding
	print 'Could be one of: "%s"' % '", "'.join(available_encodings())
	sys.exit(1)

##############################################################################

# Prepare socket
s_opts = prepare_socket(options.socket)

# Read informations from livestatus
checks = livestatus2dict(s_opts, options.host, options.service)

# Convert to XML
xmldoc = xml_from_dict(checks, options.encoding)

# Output
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

