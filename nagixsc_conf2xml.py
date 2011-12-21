#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_conf2xml.py
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
import sys

##############################################################################

import nagixsc

##############################################################################

checkresults = nagixsc.Checkresults()

parser = optparse.OptionParser()

parser.add_option('-c', '', dest='conffile', help='Config file')
parser.add_option('-o', '', dest='outfile', help='Output file name, "-" for STDOUT or HTTP POST URL')
parser.add_option('-H', '', dest='host', help='Hostname/section to search for in config file')
parser.add_option('-D', '', dest='service', help='Service description to search for in config file (needs -H)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name, if outfile is HTTP(S) URL')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password, if outfile is HTTP(S) URL')
parser.add_option('-e', '', dest='encoding', help='Encoding ("%s")' % '", "'.join(checkresults.available_encodings) )
parser.add_option('-q', '', action='store_true', dest='quiet', help='Be quiet')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(conffile=None)
parser.set_defaults(outfile='-')
parser.set_defaults(encoding='base64')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

# Check if conffile specified
if not options.conffile:
	print 'Need a conf file! Please specify one with "-c"!'
	sys.exit(3)

# Check encoding type
if not checkresults.check_encoding(options.encoding):
	print 'Wrong encoding method "%s"!' % options.encoding
	print 'Could be one of: "%s"' % '", "'.join(checkresults.available_encodings)
	sys.exit(3)

##############################################################################

# Try to read conffile
config = nagixsc.read_inifile(options.conffile)

if not config:
	print 'Config file "%s" could not be read!' % options.conffile
	sys.exit(3)

# Put necessary options to checkresults
checkresults.options['outfile'] = options.outfile
checkresults.options['hostfilter'] = options.host
checkresults.options['servicefilter'] = options.service
checkresults.options['httpuser'] = options.httpuser
checkresults.options['httppasswd'] = options.httppasswd
checkresults.options['encoding'] = options.encoding

# Execute checks, build dict
checkresults.conf2dict(config)

# Output
(status, response) = checkresults.write_xml()

plresult = nagixsc.Checkresults()
(plstatus, plresponse) = plresult.read_xml_from_string(response)

# plstatus == True if we got Nag(ix)SC XML back
if plstatus:
	plresult.xml_to_dict()
	if len(plresult.checks) != 1:
		print 'Nag(ix)SC: Need exact ONE check result in response, got %s' % len(plresult.checks)
		sys.exit(3)

	print plresult.checks[0]['output']
	sys.exit(int(plresult.checks[0]['returncode']))

# No XML => Print error message or status message if we should not be quiet
if status == False:
	print response
else:
	if not options.quiet:
		print response

