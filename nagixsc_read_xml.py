#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_read_xml.py
#
# Copyright (C) 2009-2010 Sven Velt <sv@teamix.net>
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

#import base64
import libxml2
import optparse
import sys
import time

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of status file (xml)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password')
parser.add_option('-f', '', dest='file', help='(Path and) file name of status file')
parser.add_option('-s', '', dest='seconds', type='int', help='Maximum age in seconds of xml timestamp')
parser.add_option('-m', '', action='store_true', dest='markold', help='Mark (Set state) of too old checks as UNKNOWN')
parser.add_option('-P', '', action='store_true', dest='pprint', help='Output with Python\'s pprint')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(file='-')
parser.set_defaults(seconds=14400)
parser.set_defaults(markold=False)
parser.set_defaults(pprint=False)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

from nagixsc import *

##############################################################################

now = int(time.time())

# Get URL or file
doc = read_xml(options)


# Check XML file basics
(status, string) = xml_check_version(doc)
debug(1, options.verb, string)
if not status:
	print string
	sys.exit(127)


# Get timestamp and check it
filetimestamp = xml_get_timestamp(doc)
if not filetimestamp:
	print 'No timestamp found in XML file, exiting because of invalid XML data...'
	sys.exit(127)

timedelta = int(now) - int(filetimestamp)
debug(1, options.verb, 'Age of XML file: %s seconds, max allowed: %s seconds' % (timedelta, options.seconds))


# Put XML to Python dict
checks = xml_to_dict(doc)


if options.pprint:
	# Print 'em all in one
	import pprint
	pprint.pprint(checks)
else:
	# Loop over check results and output them
	for check in checks:
		check = check_mark_outdated(check, now, options.seconds, options.markold)
		print 'Host:      %s\nService:   %s\nRetCode:   %s\nOutput:    %r\nTimestamp: %s\n' % (check['host_name'], check['service_description'], check['returncode'], check['output'], check['timestamp'])

