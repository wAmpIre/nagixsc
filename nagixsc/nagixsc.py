# Nag(ix)SC -- nagixsc/nagixsc.py
#
# Copyright (C) 2011 Sven Velt <sv@teamix.net>
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
import base64
import cStringIO
import os
import shlex
import signal
import subprocess
import time
import urllib2

from xml.dom.minidom import parseString
from xml.etree import cElementTree as ET

import http


def read_inifile(inifile):
	config = ConfigParser.RawConfigParser()
	config.optionxform = str # We need case-sensitive options
	ini_list = config.read(inifile)

	if ini_list:
		return config
	else:
		return False


##############################################################################


class ExecTimeoutError(Exception):
	pass


##############################################################################


class Checkresults(object):
	def __init__(self):
		self.available_encodings = ['base64', 'plain',]
		self.options = {}
		self.checks = []
		self.xmldoc = None
		self.encoding = None


	def debug(self, level, message):
		if self.options:
			if self.options.verbose:
				if level <= self.options.verbose:
					print "%s: %s" % (level, string)
		else:
			print "%s: %s" % (level, string)


	def check_encoding(self, encoding):
		if encoding in self.available_encodings:
			return True
		else:
			return False


	def decode(self, data, encoding='base64'):
		if encoding == 'base64':
			return base64.b64decode(data)
		elif encoding == 'plain':
			return data
		else:
			return None


	def encode(self, data, encoding='base64'):
		if encoding == 'base64':
			return base64.b64encode(data)
		elif encoding == 'plain':
			return data
		else:
			return None


	def exec_timeout_handler(self, signum, frame):
		raise ExecTimeoutError


	def exec_check(self, host_name, service_descr, cmdline, cmdprefix='', timeout=None, timeout_returncode=2):
		cmdarray = shlex.split(cmdline)

		check = {}
		check['host_name'] = host_name
		check['service_description'] = service_descr

		if len(cmdarray) == 0:
			check['output'] = 'No command line specified!'
			check['returncode'] = 127
			return check

		check['commandline'] = cmdline
		check['command'] = cmdarray[0].split(os.path.sep)[-1]

		if cmdprefix:
			check['fullcommandline'] = cmdprefix + ' ' + cmdline
			cmdarray = shlex.split(cmdprefix) + cmdarray
		else:
			check['fullcommandline'] = cmdline

		if timeout:
			signal.signal(signal.SIGALRM, exec_timeout_handler)
			signal.alarm(timeout)

		try:
			cmd = subprocess.Popen(cmdarray, stdout=subprocess.PIPE)
			check['output'] = cmd.communicate()[0].rstrip()
			check['returncode'] = cmd.returncode
		except OSError:
			check['output'] = 'Could not execute "%s"' % cmdline
			check['returncode'] = 127
		except ExecTimeoutError:
			check['output'] = 'Plugin timed out after %s seconds' % timeout
			check['returncode'] = timeout_returncode

		if timeout:
			signal.alarm(0)
			try:
				if sys.version_info >= (2, 6):
					cmd.terminate()
				else:
					os.kill(cmd.pid, 15)
			except OSError:
				pass

		check['timestamp'] = str(long(time.time()))
		return check


	def conf2dict(self, config):
		# Read "plugin_timeout" from "[nagixsc]", default "None" (no timeout)
		try:
			timeout = config.getint('nagixsc','plugin_timeout')
		except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
			timeout = None

		# Read "plugin_timeout_returncode" from "[nagixsc]", default "2" (CRITICAL)
		try:
			timeout_returncode = config.getint('nagixsc','plugin_timeout_returncode')
		except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
			timeout_returncode = 2

		# Read "add_pnp4nagios_template_hint" from "[nagixsc]", default "False"
		try:
			add_pnp4nagios_template_hint = config.getboolean('nagixsc','add_pnp4nagios_template_hint')
		except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
			add_pnp4nagios_template_hint = False

		# Read "command_prefix" from "[nagixsc]", default "" (empty string)
		try:
			cmdprefix_conffile = config.get('nagixsc','command_prefix')
		except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
			cmdprefix_conffile = ''

		# Sections are Hosts (not 'nagixsc'), options in sections are Services
		hosts = config.sections()
		if 'nagixsc' in hosts:
			hosts.remove('nagixsc')

		# Filter out host/section if it exists
		if self.options['hostfilter']:
			if self.options['hostfilter'] in hosts:
				hosts = [self.options['hostfilter'],]
			else:
				hosts = []

		for host in hosts:
			# Overwrite section/host name with '_host_name'
			if config.has_option(host,'_host_name'):
				host_name = config.get(host,'_host_name')
			else:
				host_name = host

			services = config.options(host)
			# Look for host/section specific "command_prefix"
			if '_command_prefix' in services:
				cmdprefix = config.get(host, '_command_prefix')
			else:
				cmdprefix = cmdprefix_conffile

			# Look for host check
			if '_host_check' in services and not self.options['servicefilter']:
				cmdline = config.get(host, '_host_check')
				check = self.exec_check(host_name, None, cmdline, cmdprefix, timeout, timeout_returncode)
				if add_pnp4nagios_template_hint and '|' in check['output']:
					check['output'] += ' [%s]' % check['command']
				self.checks.append(check)

			# Filter out service if given in cmd line options
			if self.options['servicefilter']:
				if self.options['servicefilter'] in services:
					services = [self.options['servicefilter'],]
				else:
					services = []

			for service in services:
				# If option starts with '_' it may be a NagixSC option in the future
				if service[0] != '_':
					cmdline = config.get(host, service)

					check = self.exec_check(host_name, service, cmdline, cmdprefix, timeout, timeout_returncode)
					if add_pnp4nagios_template_hint and '|' in check['output']:
						check['output'] += ' [%s]' % check['command']
					self.checks.append(check)


	def xml_from_dict(self):
		self.encoding = self.options.get('encoding') or 'base64'

		lasthost = None

		db = [(check['host_name'], check) for check in self.checks]
		db.sort()

		xmlroot = ET.Element('nagixsc')
		xmlroot.set('version', '1.1')
		xmltimestamp = ET.SubElement(xmlroot, 'timestamp')
		xmltimestamp.text = str(long(time.time()))

		for entry in db:
			check = entry[1]

			if check['host_name'] != lasthost:
				xmlhost = ET.SubElement(xmlroot, 'host')
				xmlhostname = ET.SubElement(xmlhost, 'name')
				xmlhostname.text = self.encode(check['host_name'], self.encoding)
				xmlhostname.set('encoding', self.encoding)
				lasthost = check['host_name']

			if check['service_description'] in ['', None, ]:
				# Host check result
				xmlbase = xmlhost
			else:
				# Service check result
				xmlservice = ET.SubElement(xmlhost, 'service')
				xmldescr = ET.SubElement(xmlservice, 'description')
				xmldescr.text = self.encode(check['service_description'], self.encoding)
				xmldescr.set('encoding', self.encoding)
				xmlbase = xmlservice

			xmlreturncode = ET.SubElement(xmlbase, 'returncode')
			xmlreturncode.text = str(check['returncode'])
			xmloutput = ET.SubElement(xmlbase, 'output')
			xmloutput.text = self.encode(check['output'], self.encoding)
			xmloutput.set('encoding', self.encoding)
			if check.has_key('timestamp'):
				xmltimestamp  = ET.SubElement(xmlbase, 'timestamp')
				xmltimestamp.text = str(check['timestamp'])

		self.xmldoc = ET.ElementTree(xmlroot)


	def write_xml(self):
		self.xml_from_dict()

		if not self.options.get('outfile'):
			return (False, 'No filename given!')

		if self.options['outfile'].startswith('http'):
			(headers, body) = nagixsc.http.encode_multipart(ET.tostring(self.xmldoc), self.options['httpuser'], self.options['httppasswd'])
			try:
				response = urllib2.urlopen(urllib2.Request(self.options['outfile'], body, headers)).read()
			except urllib2.HTTPError, error:
				return (False, error)
			except urllib2.URLError, error:
				return (False, error)

			return (True, response)

		elif self.options['outfile'] == '-':
			pseudofile = cStringIO.StringIO()
			self.xmldoc.write(pseudofile, encoding='utf-8', xml_declaration=True)
			pseudofile.reset()
			print parseString(pseudofile.read()).toprettyxml(indent='  ')
			return (True, 'Written XML to stdout')

		else:
			try:
				self.xmldoc.write(self.options['outfile'], encoding='utf-8', xml_declaration=True)
			except IOError, error:
				return (False, error)

			return (True, 'Written XML to %s' % self.options['outfile'])



