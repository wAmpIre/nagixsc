#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_xml2nagios.py
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
import time

NAGIOSCMDs = [
		'/usr/local/nagios/var/rw/nagios.cmd',
		'/var/lib/nagios3/rw/nagios.cmd',
		'/usr/local/icinga/var/rw/icinga.cmd',
		'/var/lib/icinga/rw/icinga.cmd',
		]

CHECKRESULTDIRs = [
		'/usr/local/nagios/var/spool/checkresults',
		'/var/lib/nagios3/spool/checkresults',
		'/usr/local/icinga/var/spool/checkresults',
		'/var/lib/icinga/spool/checkresults',
		]

ALLMODEs = [ 'passive', 'passive_check', 'checkresult', 'checkresult_check', 'active', ]
MODEs = [ 'passive', 'checkresult', 'active', ]

##############################################################################

import nagixsc

##############################################################################

checkresults = nagixsc.Checkresults()

parser = optparse.OptionParser()

parser.add_option('-u', '', dest='url', help='URL of status file (xml)')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password')
parser.add_option('', '--force-http-auth', action='store_true', dest='httpforceauth', help='Force HTTP authentication (may be unsecure!)')
parser.add_option('-f', '', dest='file', help='(Path and) file name of status file')
#parser.add_option('-S', '', dest='schemacheck', help='Check XML against DTD')
parser.add_option('-s', '', dest='seconds', type='int', help='Maximum age in seconds of xml timestamp')
parser.add_option('-m', '', action='store_true', dest='markold', help='Mark (Set state) of too old checks as UNKNOWN')
parser.add_option('-O', '', dest='mode', help='Where/Howto output the results ("%s")' % '", "'.join(MODEs))
parser.add_option('-P', '', dest='plugin', action='store_true', help='Act as plugin wrt output and returncode')
parser.add_option('-p', '', dest='pipe', help='Full path to nagios.cmd')
parser.add_option('-r', '', dest='checkresultdir', help='Full path to checkresult directory')
parser.add_option('-H', '', dest='host', help='Hostname to search for in XML file')
parser.add_option('-D', '', dest='service', help='Service description to search for in XML file')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(url=None)
parser.set_defaults(httpuser=None)
parser.set_defaults(httppasswd=None)
parser.set_defaults(httpforceauth=None)
parser.set_defaults(file='-')
#parser.set_defaults(schemacheck='')
parser.set_defaults(seconds=14400)
parser.set_defaults(markold=False)
parser.set_defaults(mode=None)
parser.set_defaults(pipe=None)
parser.set_defaults(checkresultdir=None)
parser.set_defaults(host=None)
parser.set_defaults(service=None)
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

# We need this option from start
checkresults.options['verbose'] = options.verb

# Also accept old modes, but output only new ones
if options.mode not in ALLMODEs:
	print 'Not an allowed mode "%s" - allowed are: "%s"' % (options.mode, '", "'.join(MODEs))
	sys.exit(2)

# Backward compatibility
if options.mode.endswith('_check'):
	options.mode = options.mode[:-6]
	options.plugin = True

# Check command line options wrt mode
if options.mode == 'passive':
	checkresults.debug(1, 'Running in passive mode')
	if options.pipe == None and options.verb <= 2:
		for nagioscmd in NAGIOSCMDs:
			if os.path.exists(nagioscmd):
				options.pipe = nagioscmd
				break

	if options.verb <= 2:
		if options.pipe == None:
			print 'Need full path to the nagios.cmd/icinga.cmd pipe (-p FILENAME)!'
			sys.exit(2)

		if not os.access(options.pipe, os.W_OK):
			print 'Command pipe at "%s" not writable!' % options.pipe
			sys.exit(2)

		checkresults.debug(2, 'Command pipe found at %s' % options.pipe)

	checkresults.options['pipe'] = options.pipe

elif options.mode == 'checkresult':
	checkresults.debug(1, 'Running in checkresult mode')
	if options.checkresultdir == None and options.verb <= 2:
		for crd in CHECKRESULTDIRs:
			if os.path.isdir(crd):
				options.checkresultdir = crd
				break

	if options.verb <= 2:
		if options.checkresultdir == None:
			print 'Need full path to the check result directory (-r DIRECTORY)!'
			sys.exit(2)

		if not os.access(options.checkresultdir, os.W_OK):
			print 'Check result directory at "%s" is not writable!' % options.checkresultdir

		checkresults.debug(2, 'Check result dir: %s' % options.checkresultdir)

	checkresults.options['checkresultdir'] = options.checkresultdir

elif options.mode == 'active':
	checkresults.debug(1, 'Running in active/plugin mode')
	if options.host == None:
		checkresults.debug(1, 'No host specified on command line')
	if options.service == None:
		checkresults.debug(1, 'No service specified on command line, looking at XML file later')

##############################################################################

# Put necessary options to checkresults
checkresults.options['url'] = options.url
checkresults.options['httpuser'] = options.httpuser
checkresults.options['httppasswd'] = options.httppasswd
checkresults.options['httpforceauth'] = options.httpforceauth
checkresults.options['file'] = options.file
checkresults.options['seconds'] = options.seconds
checkresults.options['markold'] = options.markold
checkresults.options['hostfilter'] = options.host
checkresults.options['servicefilter'] = options.service

# Get start time
starttime = time.time()

# Get URL or file
(status, response) = checkresults.read_xml()

if not status:
	print response
	sys.exit(2)

checkresults.debug(2, response)


# Calculate elapsed time
elapsedtime = time.time() - starttime

# Now timestamp AFTER getting the XML file
now = long(time.time())

# FIXME: Check XML against DTD
#if options.schemacheck:
#	dtd = libxml2.parseDTD(None, options.schemacheck)
#	ctxt = libxml2.newValidCtxt()
#	ret = doc.validateDtd(ctxt, dtd)
#	if ret != 1:
#		print "error doing DTD validation"
#		sys.exit(1)
#	dtd.freeDtd()
#	del dtd
#	del ctxt


# Check XML file basics
(status, response) = checkresults.xml_check_version()
checkresults.debug(1, response)
if not status:
	print response
	sys.exit(2)


# Get timestamp and check it
(status, response) = checkresults.xml_get_timestamp()
if not status:
	print response
	sys.exit(2)

timedelta = long(now) - long(checkresults.xmltimestamp)
checkresults.debug(1, 'Age of XML file: %s seconds, max allowed: %s seconds' % (timedelta, options.seconds))


# Put XML to Python dict
checkresults.xml_to_dict()


# Loop over check results and perhaps mark them as outdated
checkresults.mark_all_checks_outdated()


# Next steps depend on mode, output results
# MODE: passive
if options.mode == 'passive':
	(status, count_services, response) = checkresults.dict2out_passive()
	if not status:
		print response
		sys.exit(2)

	# Return/Exit as a Nagios Plugin if called with mode 'passive_check'
	if options.plugin:
		returncode = 0
		returnstring = 'OK'
		output = '%s check results written' % count_services
		perfdata = 'runtime=%.3fs;;;; services=%.0f;;;;' % (elapsedtime, count_services)

		if options.markold:
			if fileage > options.seconds:
				returnstring = 'WARNING'
				output = '%s check results written, which are %s(>%s) seconds old' % (count_services, fileage, options.seconds)
				returncode = 1

		print 'Nag(ix)SC %s - %s|%s' % (returnstring, output, perfdata)
		sys.exit(returncode)

# MODE: checkresult:
elif options.mode == 'checkresult':
	(status, count_services, count_failed, list_failed) = checkresults.dict2out_checkresult()

	returnstring = ''
	output = ''
	perfdata = 'runtime=%.3fs;;;; services=%.0f;;;;' % (elapsedtime, count_services)
	if count_failed == 0:
		returnstring = 'OK'
		returncode = 0
		output = 'Wrote checkresult files for %s services' % count_services
	elif count_failed == count_services:
		returnstring = 'CRITICAL'
		returncode = 2
		output = 'No checkresult files could be writen!'
	else:
		returnstring = 'WARNING'
		returncode = 1
		output = 'Could not write %s out of %s checkresult files!' % (count_failed, count_services)

	if options.plugin:
		print 'Nag(ix)SC %s - %s|%s' % (returnstring, output, perfdata)
		sys.exit(returncode)
	else:
		if list_failed:
			print output
			for entry in list_failed:
				print 'Could not write checkresult files "%s(.ok)" for "%s"/"%s"!' % (entry[0], entry[1], entry[2])
			sys.exit(returncode)
		else:
			sys.exit(0)

# MODE: active
elif options.mode == 'active':
	if len(checkresults.checks) > 1:
		print 'Nag(ix)SC UNKNOWN - Found more (%s) than one host/service check!' % len(checkresults.checks)
		print 'Found: ' + ', '.join(['%s/%s' % (c['host_name'], c['service_description']) for c in checkresults.checks])
		sys.exit(3)
	elif len(checkresults.checks) == 0:
		output = 'Nag(ix)SC UNKNOWN - No check found in XML'
		if options.host:
			output += ' - Host filter: "%s"' % options.host
		if options.service:
			output += ' - Service filter: "%s"' % options.service
		print output
		sys.exit(3)

	print checkresults.checks[0]['output']
	sys.exit(int(checkresults.checks[0]['returncode']))

else:
	print 'Unknown mode! This should NEVER happen!'
	sys.exit(2)

