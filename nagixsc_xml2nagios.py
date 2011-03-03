#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_xml2nagios.py
#
# Copyright (C) 2009-2010 Sven Velt <sv@teamix.net>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; only version 2 of the License is applicable.
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
import os
import sys
import time

NAGIOSCMDs = [ '/usr/local/nagios/var/rw/nagios.cmd', '/var/lib/nagios3/rw/nagios.cmd', ]
CHECKRESULTDIRs = [ '/usr/local/nagios/var/spool/checkresults', '/var/lib/nagios3/spool/checkresults', ]
MODEs = [ 'passive', 'passive_check', 'checkresult', 'checkresult_check', 'active', ]

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of status file (xml)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password')
parser.add_option('-f', '', dest='file', help='(Path and) file name of status file')
parser.add_option('-S', '', dest='schemacheck', help='Check XML against DTD')
parser.add_option('-s', '', dest='seconds', type='int', help='Maximum age in seconds of xml timestamp')
parser.add_option('-m', '', action='store_true', dest='markold', help='Mark (Set state) of too old checks as UNKNOWN')
parser.add_option('-O', '', dest='mode', help='Where/Howto output the results ("%s")' % '", "'.join(MODEs))
parser.add_option('-p', '', dest='pipe', help='Full path to nagios.cmd')
parser.add_option('-r', '', dest='checkresultdir', help='Full path to checkresult directory')
parser.add_option('-H', '', dest='host', help='Hostname to search for in XML file')
parser.add_option('-D', '', dest='service', help='Service description to search for in XML file')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(file='nagixsc.xml')
parser.set_defaults(schemacheck='')
parser.set_defaults(seconds=14400)
parser.set_defaults(markold=False)
parser.set_defaults(mode=False)
parser.set_defaults(pipe=None)
parser.set_defaults(checkresultdir=None)
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

from nagixsc import *

##############################################################################

if options.mode not in MODEs:
	print 'Not an allowed mode "%s" - allowed are: "%s"' % (options.mode, '", "'.join(MODEs))
	sys.exit(127)

# Check command line options wrt mode
if options.mode == 'passive' or options.mode == 'passive_check':
	debug(1, options.verb, 'Running in passive mode')
	if options.pipe == None and options.verb <= 2:
		for nagioscmd in NAGIOSCMDs:
			if os.path.exists(nagioscmd):
				options.pipe = nagioscmd

	if options.pipe == None and options.verb <= 2:
		print 'Need full path to the nagios.cmd pipe!'
		sys.exit(127)

	debug(2, options.verb, 'nagios.cmd found at %s' % options.pipe)

elif options.mode == 'checkresult' or options.mode == 'checkresult_check':
	debug(1, options.verb, 'Running in checkresult mode')
	if options.checkresultdir == None and options.verb <= 2:
		for crd in CHECKRESULTDIRs:
			if os.path.exists(crd):
				options.checkresultdir = crd

	if options.checkresultdir == None and options.verb <= 2:
		print 'Need full path to the checkresultdir!'
		sys.exit(127)

	debug(2, options.verb, 'Checkresult dir: %s' % options.checkresultdir)

elif options.mode == 'active':
	debug(1, options.verb, 'Running in active/plugin mode')
	if options.host == None:
		debug(1, options.verb, 'No host specified on command line')
	if options.service == None:
		debug(1, options.verb, 'No service specified on command line, looking at XML file later')

##############################################################################

# Get URL or file
doc = read_xml(options)

# Now timestamp AFTER getting the XML file
now = long(time.time())


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


# Get timestamp and check it
filetimestamp = xml_get_timestamp(doc)
if not filetimestamp:
	print 'No timestamp found in XML file, exiting because of invalid XML data...'
	sys.exit(127)

timedelta = int(now) - int(filetimestamp)
debug(1, options.verb, 'Age of XML file: %s seconds, max allowed: %s seconds' % (timedelta, options.seconds))


# Put XML to Python dict
checks = xml_to_dict(doc, options.verb, options.host, options.service)

# Loop over check results and perhaps mark them as outdated
for check in checks:
	check = check_mark_outdated(check, now, options.seconds, options.markold)


# Next steps depend on mode, output results
# MODE: passive
if options.mode == 'passive' or options.mode == 'passive_check':
	count_services = dict2out_passive(checks, xml_get_timestamp(doc), options.pipe, options.verb)

	# Return/Exit as a Nagios Plugin if called with mode 'passive_check'
	if options.mode == 'passive_check':
		returncode   = 0
		returnstring = 'OK'
		output       = '%s check results written which are %s seconds old' % (count_services, (now-filetimestamp))

		if options.markold:
			if (now - filetimestamp) > options.seconds:
				returnstring = 'WARNING'
				output = '%s check results written, which are %s(>%s) seconds old' % (count_services, (now-filetimestamp), options.seconds)
				returncode = 1

		print 'Nag(ix)SC %s - %s' % (returnstring, output)
		sys.exit(returncode)

# MODE: checkresult: "checkresult", "checkresult_check"
elif options.mode.startswith('checkresult'):
	(count_services, count_failed, list_failed) = dict2out_checkresult(checks, xml_get_timestamp(doc), options.checkresultdir, options.verb)

	if options.mode == 'checkresult':
		if list_failed:
			for entry in list_failed:
				print 'Could not write checkresult files "%s(.ok)" for "%s"/"%s"!' % (entry[0], entry[1], entry[2])

		if count_failed == 0:
			sys.exit(0)
		else:
			sys.exit(1)

	elif options.mode == 'checkresult_check':
		returnstring = ''
		output       = ''
		if count_failed == 0:
			returnstring = 'OK'
			returncode   = 0
			output       = 'Wrote checkresult files for %s services' % count_services
		elif count_failed == count_services:
			returnstring = 'CRITICAL'
			returncode   = 2
			output       = 'No checkresult files could be writen!'
		else:
			returnstring = 'WARNING'
			returncode   = 1
			output       = 'Could not write %s out of %s checkresult files!' % (count_failed, count_services)

		print 'Nag(ix)SC %s - %s' % (returnstring, output)
		sys.exit(returncode)

# MODE: active
elif options.mode == 'active':

	if len(checks) > 1:
		print 'Nag(ix)SC UNKNOWN - Found more (%s) than one host/service!' % len(checks)
		print 'Found: ' + ', '.join(['%s/%s' % (c['host_name'], c['service_description']) for c in checks])
		sys.exit(3)
	elif len(checks) == 0:
		output = 'Nag(ix)SC UNKNOWN - No check found in XML'
		if options.host:
			output += ' - Host filter: "%s"' % options.host
		if options.service:
			output += ' - Service filter: "%s"' % options.service
		print output
		sys.exit(3)

	print checks[0]['output']
	sys.exit(int(checks[0]['returncode']))

else:
	print 'Unknown mode! This should NEVER happen!'
	sys.exit(127)

