#!/usr/bin/python

import ConfigParser
import optparse
import sys

##############################################################################

from nagixsc import *

##############################################################################

checks = []


parser = optparse.OptionParser()

parser.add_option('-c', '', dest='conffile', help='Config file')
parser.add_option('-o', '', dest='outfile', help='Output file')
parser.add_option('-e', '', dest='encoding', help='Encoding ("%s")' % '", "'.join(available_encodings()) )
parser.add_option('-H', '', dest='host', help='Hostname/section to search for in config file')
parser.add_option('-D', '', dest='service', help='Service description to search for in config file (needs -H)')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(conffile='nagixsc.conf')
parser.set_defaults(outfile='-')
parser.set_defaults(encoding='base64')
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

if options.encoding not in available_encodings():
	print 'Wrong encoding method "%s"!' % options.encoding
	print 'Could be one of: %s' % ', '.join(available_encodings)
	sys.exit(127)

##############################################################################

config = ConfigParser.RawConfigParser()
config.optionxform = str # We need case-sensitive options
conf_list = config.read(options.conffile)

if conf_list == []:
	print 'Config file "%s" could not be read!' % options.conffile
	sys.exit(127)

# Sections are Hosts (not 'nagixsc'), options in sections are Services
hosts = config.sections()
if 'nagixsc' in hosts:
	hosts.remove('nagixsc')

# Filter out host/section if it exists
if options.host:
	if options.host in hosts:
		hosts = [options.host,]
	else:
		hosts = []

for host in hosts:
	# Overwrite section/host name with '_host_name'
	if config.has_option(host,'_host_name'):
		host_name = config.get(host,'_host_name')
	else:
		host_name = host


	services = config.options(host)
	# Look for host check
	if '_host_check' in services and not options.service:
		cmdline = config.get(host, '_host_check')
		check = exec_check(host_name, None, cmdline)
		checks.append(check)


	# Filter out service if it exists
	if options.service:
		if options.service in services:
			services = [options.service,]
		else:
			services = []

	for service in services:
		# If option starts with '_' it may be a NagixSC option in the future
		if service[0] != '_':
			cmdline = config.get(host, service)

			check = exec_check(host_name, service, cmdline)
			checks.append(check)


xmldoc = xml_from_dict(checks, options.encoding)
if options.outfile == '-':
	xmldoc.saveFormatFile('-', format=1)
else:
	xmldoc.saveFile(options.outfile)


