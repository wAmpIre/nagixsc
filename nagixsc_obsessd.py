#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_obsessd.py
#
# Copyright (C) 2010-2012 Sven Velt <sv@teamix.net>
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

import ConfigParser
import cStringIO
import optparse
import os
import re
import sys
import time

##############################################################################

import nagixsc

##############################################################################

defaults4cfgfile = cStringIO.StringIO('''
[daemon]
interval: 5
spooldir: /tmp/nagixsc.spool
spooldir_new: %(spooldir)s/new
spooldir_work: %(spooldir)s/work
spooldir_done: %(spooldir)s/done
spooldir_xml: %(spooldir)s/xml
keep_spoolfiles: True
keep_xmlfiles: True
pidfile: /var/run/nagixsc_obsessd.pid
[target]
url:
user:
password:
''')


##############################################################################

service_analyzer = "^LASTSERVICECHECK::(?P<timestamp>\d+)\s+"
service_analyzer += "HOSTNAME::'(?P<host_name>[^']+)'\s+"
service_analyzer += "SERVICEDESC::'(?P<service_description>[^']+)'\s+"
service_analyzer += "SERVICESTATEID::(?P<returncode>\d+)\s+"
service_analyzer += "SERVICEOUTPUT::'(?P<output>[^']*)'\s+"
service_analyzer += "SERVICEPERFDATA::'(?P<perfdata>[^']*)'\s+"
service_analyzer += "LONGSERVICEOUTPUT::'(?P<longoutput>[^']*)'"
service_analyzer = re.compile(service_analyzer, re.MULTILINE)

host_analyzer = "^LASTHOSTCHECK::(?P<timestamp>\d+)\s+"
host_analyzer += "HOSTNAME::'(?P<host_name>[^']+)'\s+"
host_analyzer += "HOSTSTATEID::(?P<returncode>\d+)\s+"
host_analyzer += "HOSTOUTPUT::'(?P<output>[^']*)'\s+"
host_analyzer += "HOSTPERFDATA::'(?P<perfdata>[^']*)'\s+"
host_analyzer += "LONGHOSTOUTPUT::'(?P<longoutput>[^']*)'"
host_analyzer = re.compile(host_analyzer, re.MULTILINE)


##############################################################################

def read_config_file_daemon(cfgread):
	config = {}

	for parm in ['spooldir', 'spooldir_new', 'spooldir_work', 'spooldir_done', 'spooldir_xml']:
		try:
			config[parm] = cfgread.get('daemon', parm)
		except ConfigParser.NoSectionError, ConfigParser.NoOptionError:
			print 'Could not read option "%s" from config file' % parm
			sys.exit(1)

	for parm in ['keep_spoolfiles', 'keep_xmlfiles']:
		try:
			config[parm] = cfgread.getboolean('daemon', parm)
		except ConfigParser.NoSectionError, ConfigParser.NoOptionError:
			print 'Could not read option "%s" from config file' % parm
			sys.exit(1)
		except ConfigParser.ValueError:
			print 'Value for "%s" not boolean: %s' % (parm, cfgread.get('daemon', parm))
			sys.exit(1)

	for parm in ['interval', ]:
		try:
			config[parm] = cfgread.getint('daemon', parm)
		except ConfigParser.NoSectionError, ConfigParser.NoOptionError:
			print 'Could not read option "%s" from config file' % parm
			sys.exit(1)
		except ConfigParser.ValueError:
			print 'Value for "%s" not integer: %s' % (parm, cfgread.get('daemon', parm))
			sys.exit(1)

	return config


def read_config_file_one_target(cfgread, targetname):
	target = {}

	for parm in ['url', 'user', 'password']:
		try:
			target[parm] = cfgread.get(targetname, parm)
		except ConfigParser.NoSectionError, ConfigParser.NoOptionError:
			print 'Target "%s": Could not read "%s"' % (targetname, parm)
			sys.exit(1)

	return target


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


def check_target(target):
	return True


def read_obsess_file(filename):
	checks = []
	content = open(filename).read()
	print 'Read ' + filename

	for match in service_analyzer.finditer(content):
		check = match.groupdict()
		if check['longoutput']:
			check['output'] += '\n' + check['longoutput']
			check.pop('longoutput')
		if check['perfdata']:
			check['output'] += '|' + check['perfdata']
			check.pop('perfdata')
		checks.append(check)

	for match in host_analyzer.finditer(content):
		check = match.groupdict()
		check['service_description'] = None
		if check['longoutput']:
			check['output'] += '\n' + check['longoutput']
			check.pop('longoutput')
		if check['perfdata']:
			check['output'] += '|' + check['perfdata']
			check.pop('perfdata')
		checks.append(check)

	print "Read %s check result(s)" % len(checks)
	return checks


def old_read_obsess_file(filename):
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
			else:
				print 'FAIL_SRV: ' + line
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
				print 'FAIL_HST: ' + line
		else:
			print 'FAIL: ' + line
		count_lines += 1

	print "Read %s lines" % count_lines
	f.close()
	return checks


##############################################################################

def main():
	# Command line options
	parser = optparse.OptionParser()

	parser.add_option('-c', '', dest='cfgfile', help='Config file')
	parser.add_option('-d', '--daemon', action='store_true', dest='daemon', help='Daemonize, go to background')
	parser.add_option('', '--nossl', action='store_true', dest='nossl', help='Disable SSL (overwrites config file)')

	parser.set_defaults(cfgfile='/etc/nagixsc/obsessd.cfg')

	(options, args) = parser.parse_args()

	# Config file: Prepare read, set defaults
	cfgread = ConfigParser.SafeConfigParser()
	cfgread.optionxform = str # We need case-sensitive options
	cfgread.readfp(defaults4cfgfile)

	# Config file: (Try to) read real config file
	cfgread_list = cfgread.read(options.cfgfile)

	if cfgread_list == []:
		print 'Config file "%s" could not be read!' % options.cfgfile
		sys.exit(1)

	# Config file: Read daemon config
	config = read_config_file_daemon(cfgread)
	print config

	for d in ['spooldir', 'spooldir_new', 'spooldir_work', 'spooldir_done', 'spooldir_xml']:
		check_dir(config[d])

	# Config file: Read target(s)
	targets = []
	for section in cfgread.sections():
		if section.startswith('target'):
			target = read_config_file_one_target(cfgread, section)
			check_target(target)
			targets.append(target)

	if len(targets) == 0:
		print 'No targets found in config file!'
		sys.exit(1)

	print targets

	# Daemonize
	if options.daemon:
		nagixsc.daemon.daemonize(pidfile=server.config_server['pidfile'])

	# Prepare
	checkresults = nagixsc.Checkresults()
	files_done = []

	# Check if there are old files in "work" - they didn't get sent!
	print 'Startup...'
	if os.listdir(config['spooldir_work']):
		for filename in os.listdir(config['spooldir_work']):
			spoolfile = os.path.join(config['spooldir_work'], filename)
			checkresults.checks.extend(read_obsess_file(spoolfile))
			files_done.append(filename)
		print 'Reloaded %d check results form work dir' % len(checkresults.checks)

	# Main loop
	print 'Main loop...'
	while True:
		if os.listdir(config['spooldir_new']):
			for filename in os.listdir(config['spooldir_new']):
				spoolfile = os.path.join(config['spooldir_work'], filename)
				os.rename(os.path.join(config['spooldir_new'], filename), spoolfile)

				# Work with file
				checkresults.checks.extend(read_obsess_file(spoolfile))
				files_done.append(filename)
		print 'Got %d check results for submitting' % len(checkresults.checks)

		if len(checkresults.checks):
			# Build XML
			checkresults.xml_from_dict()
			checkresults.xml_to_string()

			# Write to File
			if config['keep_xmlfiles']:
				outfilename = '%i.xml' % time.time()
				(status, response) = checkresults.write_xml(os.path.join(config['spooldir_xml'], outfilename))
				if status:
					print 'Written ' + outfilename
				else:
					print 'COULD NOT write ' + outfilename

			# Write to http2nagios
			overall_status = True
			for target in targets:
				(status, response) = checkresults.write_xml(target['url'], target['user'], target['password'])
				if status:
					print 'Send data to %s' % target['url']
				else:
					print response
					overall_status = False

			if overall_status:
				for filename in files_done:
					os.rename(os.path.join(config['spooldir_work'], filename), os.path.join(config['spooldir_done'], filename))
				checkresults.checks = []
				files_done = []

		print "\n"
		time.sleep(config['interval'])

##############################################################################


if __name__ == '__main__':
	main()

