#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_read_xml.py
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
import time

##############################################################################

import nagixsc

##############################################################################

checkresults = nagixsc.Checkresults()

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of xml status file')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password')
parser.add_option('', '--force-http-auth', action='store_true', dest='httpforceauth', help='Force HTTP authentication (may be unsecure!)')
parser.add_option('-f', '', dest='file', help='(Path and) file name of xml status file')
parser.add_option('-s', '', dest='seconds', type='int', help='Maximum age in seconds of xml timestamp')
parser.add_option('-m', '', action='store_true', dest='markold', help='Mark (Set state) of too old checks as UNKNOWN')
parser.add_option('-P', '', action='store_true', dest='pprint', help='Output with Python\'s pprint')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(httpforceauth=False)
parser.set_defaults(file='-')
parser.set_defaults(seconds=14400)
parser.set_defaults(markold=False)
parser.set_defaults(pprint=False)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

now = long(time.time())

# Put necessary options to checkresults
checkresults.options['url'] = options.url
checkresults.options['httpuser'] = options.httpuser
checkresults.options['httppasswd'] = options.httppasswd
checkresults.options['httpforceauth'] = options.httpforceauth
checkresults.options['file'] = options.file
checkresults.options['seconds'] = options.seconds
checkresults.options['markold'] = options.markold
checkresults.options['pprint'] = options.pprint
checkresults.options['verbose'] = options.verb

# Get URL or file
(status, response) = checkresults.read_xml()

if not status:
	print response
	sys.exit(127)


# Check XML file basics
(status, response) = checkresults.xml_check_version()
checkresults.debug(1, response)
if not status:
	print string
	sys.exit(3)


# Get timestamp and check it
(status, response) = checkresults.xml_get_timestamp()
if not status:
	print response
	sys.exit(127)

timedelta = long(now) - long(checkresults.xmltimestamp)
checkresults.debug(1, 'Age of XML file: %s seconds, max allowed: %s seconds' % (timedelta, options.seconds))


# Put XML to Python dict
checkresults.xml_to_dict()


if options.pprint:
	# Print 'em all in one
	import pprint
	pprint.pprint(checks)
else:
	# Loop over check results and output them
	for check in checkresults.checks:
		check = checkresults.check_mark_outdated(check)
		print 'Host:      %s\nService:   %s\nRetCode:   %s\nOutput:    %r\nTimestamp: %s\n' % (check['host_name'], check['service_description'], check['returncode'], check['output'], check['timestamp'])

