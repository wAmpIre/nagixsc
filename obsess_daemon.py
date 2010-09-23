#!/usr/bin/python

import os
import re
import sys
import time

##############################################################################
from nagixsc import *
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

	for line in f:
		if line.startswith('LASTSERVICECHECK'):
			m = service_analyzer.match(line)
			if m:
				checks.append({'host_name':m.group(2), 'service_description':m.group(3), 'returncode':m.group(4), 'output':'\n'.join(m.group(5,6)), 'timestamp':m.group(1)})

		elif line.startswith('LASTHOSTCHECK'):
			m = host_analyzer.match(line)
			if m:
				checks.append({'host_name':m.group(2), 'service_description':None, 'returncode':m.group(3), 'output':'\n'.join(m.group(4,5)), 'timestamp':m.group(1)})
		else:
			print 'FAIL: ' + line

	f.close()
	return checks


##############################################################################

if len(sys.argv) != 4:
	print 'Please call script as: "%s http://SERVER:PORT/ username password"\n' % sys.argv[0]
	print '... with "http://SERVER:PORT/" your conf2http-URL'
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

service_analyzer = re.compile("^LASTSERVICECHECK::'?(\d+)'?\s+HOSTNAME::'?([^']+)'?\s+SERVICEDESC::'?([^']+)'?\s+SERVICESTATEID::'?(\d+)'?\s+SERVICEOUTPUT::'?([^']*)'?\s+LONGSERVICEOUTPUT::'?([^']*)'?$")
host_analyzer = re.compile("LASTHOSTCHECK::'?(\d+)'?\s+HOSTNAME::'?([^']+)'?\s+HOSTSTATEID::'?(\d+)'?\s+HOSTOUTPUT::'?([^']*)'?\s+LONGHOSTOUTPUT::'?([^']*)'?$")

# Prepare
checks = []
files_done = []

# Check if there are old files in "work" - they didn't get sent!
print 'Startup...'
if os.listdir(spoolpath_work):
	for filename in os.listdir(spoolpath_work):
		spoolfile = os.path.join(spoolpath_work, filename)
		checks.extend(read_obsess_file(spoolfile))
		files_done.append(filename)
	print 'Reloaded %d check results form work dir' % len(checks)


print 'Main loop...'
while True:
	if os.listdir(spoolpath_new):
		for filename in os.listdir(spoolpath_new):
			spoolfile = os.path.join(spoolpath_work, filename)
			os.rename(os.path.join(spoolpath_new, filename), spoolfile)

			# Work with file
			checks.extend(read_obsess_file(spoolfile))
			files_done.append(filename)
	print 'Got %d check results for submitting' % len(checks)

	if len(checks):
		xmldoc = xml_from_dict(checks)

		# Write to File
		outfilename = str(int(time.time())) + '.xml'
		write_xml(xmldoc, os.path.join(outdir, outfilename), None, None)
		print 'Written ' + outfilename

		# Write to http2nagios
		try:
			write_xml(xmldoc, sys.argv[1], sys.argv[2], sys.argv[3])
		except urllib2.URLError, error:
			print error[0]
		else:
			for filename in files_done:
				os.rename(os.path.join(spoolpath_work, filename), os.path.join(spoolpath_done, filename))
			checks = []
			files_done = []

	time.sleep(5)

