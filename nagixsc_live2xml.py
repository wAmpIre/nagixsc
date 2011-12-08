#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_live2xml.py
#
# Copyright (C) 2009-2011 Sven Velt <sv@teamix.net>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import optparse
import os
import sys

LIVESOCKETs = [
		'/usr/local/nagios/var/rw/live',
		'/var/lib/nagios3/rw/live',
		'/usr/local/icinga/var/rw/live',
		'/var/lib/icinga/rw/live',
		]

##############################################################################

import nagixsc
import nagixsc.livestatus

##############################################################################

checkresults = nagixsc.Checkresults()

parser = optparse.OptionParser()

parser.add_option('-s', '', dest='socket', help='Livestatus socket to connect')
parser.add_option('-o', '', dest='outfile', help='Output file name, "-" for STDOUT or HTTP POST URL')
parser.add_option('-e', '', dest='encoding', help='Encoding ("%s")' % '", "'.join(checkresults.available_encodings) )
parser.add_option('-H', '', dest='host', help='Hostname/section to search for in config file')
parser.add_option('-D', '', dest='service', help='Service description to search for in config file (needs -H)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name, if outfile is HTTP(S) URL')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password, if outfile is HTTP(S) URL')
parser.add_option('-q', '', action='store_true', dest='quiet', help='Be quiet')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(socket=None)
parser.set_defaults(outfile='-')
parser.set_defaults(encoding='base64')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

# We need this option from start
checkresults.options['verbose'] = options.verb

if options.socket == None:
	for livesocket in LIVESOCKETs:
		if os.path.exists(livesocket):
			options.socket = livesocket
			break

	if options.socket == None:
		print 'Need full path and name of livestatus socket (-s SOCKET)!'
		sys.exit(2)

if not os.access(options.socket, os.R_OK):
	print 'Livestatus socket at "%s" not readable!' % options.socket
	sys.exit(2)

checkresults.debug(2, 'Livestatus socket found at %s' % options.socket)

# Check encoding type
if not checkresults.check_encoding(options.encoding):
	print 'Wrong encoding method "%s"!' % options.encoding
	print 'Could be one of: "%s"' % '", "'.join(checkresults.available_encodings)
	sys.exit(3)

##############################################################################

# Put necessary options to checkresults
checkresults.options['outfile'] = options.outfile
checkresults.options['hostfilter'] = options.host
checkresults.options['servicefilter'] = options.service
checkresults.options['httpuser'] = options.httpuser
checkresults.options['httppasswd'] = options.httppasswd
checkresults.options['encoding'] = options.encoding

# Prepare socket
socket_params = nagixsc.livestatus.prepare_socket(options.socket)

# Read informations from livestatus
(status, result) = nagixsc.livestatus.livestatus2dict(socket_params, options.host, options.service)

if status == False:
	print result
	sys.exit(2)

checkresults.checks = result

# Convert to XML
#checkresults.xml_from_dict()

# Output
(status, response) = checkresults.write_xml()

# Print error message or status message if we should not be quiet
if status == False:
	print response
	sys.exit(2)

