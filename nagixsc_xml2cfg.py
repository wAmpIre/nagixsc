#!/usr/bin/python

#import base64
import libxml2
import optparse
import socket
import sys

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of status file (xml)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password')
parser.add_option('-f', '', dest='file', help='(Path and) file name of status file')
parser.add_option('-S', '', dest='schemacheck', help='Check XML against DTD')
parser.add_option('-H', '', dest='host', help='Hostname to search for in XML file')
parser.add_option('-D', '', dest='service', help='Service description to search for in XML file')
parser.add_option('', '--host-template', dest='tmpl_host', help='Filename of host template')
parser.add_option('', '--service-template', dest='tmpl_service', help='Filename of service template')
parser.add_option('-O', '', dest='output', help='Output "hosts", "services" or "both" (default)')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(file='nagixsc.xml')
parser.set_defaults(schemacheck='')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(output=None)
parser.set_defaults(tmpl_host=None)
parser.set_defaults(tmpl_service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

# Hard coded default for host template
HOSTTEMPL='''define host {
	use		templ_host_default

	host_name	%(host_name)s
	address		%(address)s
}
'''

# Hard coded default for service template
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

# Output
if not options.output in [None, 'both', 'hosts', 'services']:
	print 'Unknown output mode "%s"!' % options.output
	sys.exit(1)

if options.output in [None, 'both']:
	options.output = ['hosts', 'services']
else:
	options.output = [options.output,]

# Read host and/or service template
if options.tmpl_host and 'hosts' in options.output:
	HOSTTEMPL = open(options.tmpl_host).read()
if options.tmpl_service and 'services' in options.output:
	SERVICETEMPL = open(options.tmpl_service).read()

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


# Set default socket options
if hasattr(socket, 'setdefaulttimeout'):
	socket.setdefaulttimeout(2)

# Loop over check results and search for new hosts and new services
foundhosts = []

for check in checks:
	if not check['host_name'] in foundhosts:
		foundhosts.append(check['host_name'])

		if 'hosts' in options.output:
			try:
				check['address'] = socket.gethostbyname(check['host_name'])
			except socket.gaierror:
				check['address'] = '127.0.0.1'
			print HOSTTEMPL % check

	if check['service_description'] and 'services' in options.output:
		print SERVICETEMPL % check

