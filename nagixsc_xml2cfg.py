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
parser.add_option('-S', '', dest='schemacheck', help='Check XML against DTD')
parser.add_option('-H', '', dest='host', help='Hostname to search for in XML file')
parser.add_option('-D', '', dest='service', help='Service description to search for in XML file')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(file='nagixsc.xml')
parser.set_defaults(schemacheck='')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
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
doc = read_xml(options)

# Check XML against DTD
if options.schemacheck:
	dtd = libxml2.parseDTD(None, options.schemacheck)
	ctxt = libxml2.newValidCtxt()
	ret = doc.validateDtd(ctxt, dtd)
	if ret != 1:
		print "error doing DTD validation"
		sys.exit(1)
	dtd.freeDtd()
	del dtd
	del ctxt


# Check XML file basics
(status, statusstring) = xml_check_version(doc)
debug(1, options.verb, statusstring)
if not status:
	print statusstring
	sys.exit(127)


# Put XML to Python dict
checks = xml_to_dict(doc, options.verb, options.host, options.service)


# Loop over check results and search for new hosts and new services
foundhosts = []

for check in checks:
	if not check['host_name'] in foundhosts:
		foundhosts.append(check['host_name'])

		print HOSTTEMPL % check

	if check['service_description']:
		print SERVICETEMPL % check

