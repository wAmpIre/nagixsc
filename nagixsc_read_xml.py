#!/usr/bin/python

#import base64
import datetime
import libxml2
import optparse
import sys

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of status file (xml)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password')
parser.add_option('-f', '', dest='file', help='(Path and) file name of status file')
parser.add_option('-s', '', dest='seconds', type='int', help='Maximum age in seconds of xml timestamp')
parser.add_option('-m', '', action='store_true', dest='markold', help='Mark (Set state) of too old checks as UNKNOWN')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(file='nagixsc.xml')
parser.set_defaults(seconds=14400)
parser.set_defaults(markold=False)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

from nagixsc import *

##############################################################################

now = int(datetime.datetime.now().strftime('%s'))

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


# Loop over check results and output them
for check in checks:
	check = check_mark_outdated(check, now, options.seconds, options.markold)
	print 'Host:      %s\nService:   %s\nRetCode:   %s\nOutput:    %r\nTimestamp: %s\n' % (check['host_name'], check['service_description'], check['returncode'], check['output'], check['timestamp'])

import pprint
pprint.pprint(checks)
