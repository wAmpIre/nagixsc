#!/usr/bin/python

#import base64
import datetime
import libxml2
import optparse
import sys

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of status file (xml)')
parser.add_option('-f', '', dest='file', help='(Path and) file name of status file')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(file='nagixsc.xml')
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

HOSTTEMPL='''define host {
	use		templ_host_default

	host_name	%(host_name)s
	address		127.0.0.1
}
'''

SERVICETEMPL='''define service {
	use			templ_service_passive

	host_name		%(host_name)s
	service_description	%(service_description)s
	check_command		check_passive
}
'''

##############################################################################

from nagixsc import *

##############################################################################

# Get URL or file
if options.url != None:
	import urllib2

	response = urllib2.urlopen(options.url)
	doc = libxml2.parseDoc(response.read())
	response.close()
else:
	doc = libxml2.parseFile(options.file)


# Check XML file basics
(status, string) = xml_check_version(doc)
debug(1, options.verb, string)
if not status:
	print string
	sys.exit(127)


# Put XML to Python dict
checks = xml_to_dict(doc)


# Loop over check results and search for new hosts and new services
foundhosts = []

for check in checks:
	if not check['host_name'] in foundhosts:
		foundhosts.append(check['host_name'])

		print HOSTTEMPL % check

	if check['service_description']:
		print SERVICETEMPL % check

