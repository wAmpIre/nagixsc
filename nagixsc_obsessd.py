#!/usr/bin/python
#
# Nag(ix)SC -- obsess_daemon.py
#
# Copyright (C) 2010 Sven Velt <sv@teamix.net>
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

import os
import re
import sys
import time

##############################################################################

import nagixsc

##############################################################################

def check_dir(dirpath):
	if not os.path.isdir(dirpath):
		# dirpath does not exist, try to create it
		try:
			os.path.os.mkdir(dirpath, 0777) # FIXME
		except OSError:
			print 'Could not create directory "%s"!' % dirpath
			sys.exit(1)

	if not os.access(dirpath,os.W_OK):
		# dirpath is not writeable
		print 'No write access to directory "%s"!' % dirpath
		sys.exit(1)


def read_obsess_file(filename):
	checks = []
	f = open(filename)
	print 'Read ' + filename
	count_lines = 0

	for line in f:
		if line.startswith('LASTSERVICECHECK'):
			m = service_analyzer.match(line)
			if m:
				check = m.groupdict()
				if check['longoutput']:
					check['output'] += '\n' + check['longoutput']
					check.pop('longoutput')
				if check['perfdata']:
					check['output'] += '|' + check['perfdata']
					check.pop('perfdata')
				checks.append(check)
		elif line.startswith('LASTHOSTCHECK'):
			m = host_analyzer.match(line)
			if m:
				check = m.groupdict()
				check['service_description'] = None
				if check['longoutput']:
					check['output'] += '\n' + check['longoutput']
					check.pop('longoutput')
				if check['perfdata']:
					check['output'] += '|' + check['perfdata']
					check.pop('perfdata')
				checks.append(check)
		else:
			print 'FAIL: ' + line
		count_lines += 1

	print "Read %s lines" % count_lines
	f.close()
	return checks


##############################################################################

if len(sys.argv) != 4:
	print 'Please call script as: "%s http://SERVER:PORT/ username password"\n' % sys.argv[0]
	print '... with "http://SERVER:PORT/" your http2nagios-URL'
	print '... and "username"/"password" authentication data for it'
	sys.exit(1)

spoolpath_base = '/tmp/nagixsc.spool'
spoolpath_new = os.path.join(spoolpath_base, 'new')
spoolpath_work = os.path.join(spoolpath_base, 'work')
spoolpath_done = os.path.join(spoolpath_base, 'done')

for d in [spoolpath_base, spoolpath_new, spoolpath_work, spoolpath_done]:
	check_dir(d)

# Output XML files to this directory
outdir = os.path.join(spoolpath_base, 'xmlout')
check_dir(outdir)

service_analyzer = "^LASTSERVICECHECK::(?P<timestamp>\d+)\s+"
service_analyzer += "HOSTNAME::'(?P<host_name>[^']+)'\s+"
service_analyzer += "SERVICEDESC::'(?P<service_description>[^']+)'\s+"
service_analyzer += "SERVICESTATEID::(?P<returncode>\d+)\s+"
service_analyzer += "SERVICEOUTPUT::'(?P<output>[^']*)'\s+"
service_analyzer += "SERVICEPERFDATA::'(?P<perfdata>[^']*)'\s+"
service_analyzer += "LONGSERVICEOUTPUT::'(?P<longoutput>[^']*)'"
service_analyzer = re.compile(service_analyzer)

host_analyzer = "LASTHOSTCHECK::(?P<timestamp>\d+)\s+"
host_analyzer += "HOSTNAME::'(?P<host_name>[^']+)'\s+"
host_analyzer += "HOSTSTATEID::(?P<returncode>\d+)\s+"
host_analyzer += "HOSTOUTPUT::'(?P<output>[^']*)'\s+"
host_analyzer += "HOSTPERFDATA::'(?P<perfdata>[^']*)'\s+"
host_analyzer += "LONGHOSTOUTPUT::'(?P<longoutput>[^']*)'"
host_analyzer = re.compile(host_analyzer)

# Prepare
checkresults = nagixsc.Checkresults()
files_done = []

# Put options to checkresults
checkresults.options['httpuser'] = sys.argv[2]
checkresults.options['httppasswd'] = sys.argv[3]

# Check if there are old files in "work" - they didn't get sent!
print 'Startup...'
if os.listdir(spoolpath_work):
	for filename in os.listdir(spoolpath_work):
		spoolfile = os.path.join(spoolpath_work, filename)
		checkresults.checks.extend(read_obsess_file(spoolfile))
		files_done.append(filename)
	print 'Reloaded %d check results form work dir' % len(checkresults.checks)


print 'Main loop...'
while True:
	if os.listdir(spoolpath_new):
		for filename in os.listdir(spoolpath_new):
			spoolfile = os.path.join(spoolpath_work, filename)
			os.rename(os.path.join(spoolpath_new, filename), spoolfile)

			# Work with file
			checkresults.checks.extend(read_obsess_file(spoolfile))
			files_done.append(filename)
	print 'Got %d check results for submitting' % len(checkresults.checks)

	if len(checkresults.checks):
		# Build XML
		checkresults.xml_from_dict()
		checkresults.xml_to_string()

		# Write to File
		outfilename = '%i.xml' % time.time()
		checkresults.options['outfile'] = os.path.join(outdir, outfilename)
		(status, response) = checkresults.write_xml()
		if status:
			print 'Written ' + outfilename
		else:
			print 'COULD NOT write ' + outfilename

		# Write to http2nagios
		checkresults.options['outfile'] = sys.argv[1]
		(status, response) = checkresults.write_xml()
		if not status:
			print response
		else:
			for filename in files_done:
				os.rename(os.path.join(spoolpath_work, filename), os.path.join(spoolpath_done, filename))
			checkresults.checks = []
			files_done = []

	time.sleep(5)

