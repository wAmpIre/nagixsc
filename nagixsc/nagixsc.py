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
import random
import shlex
import signal
import string
import subprocess
import sys
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
		self.xmltimestamp = None
		self.encoding = None


	def debug(self, level, message):
		if self.options:
			if self.options.get('verbose'):
				if level <= self.options['verbose']:
					print "%s: %s" % (level, message)
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


	def reset_future_timestamp(self, timestamp):
		now = long(time.time())
		timestamp = long(timestamp)

		if timestamp <= now:
			return timestamp
		else:
			return now


	def mark_all_checks_outdated(self):
		now=long(time.time())
		for check in self.checks:
			check = self.mark_one_check_outdated(check)

		return


	def mark_one_check_outdated(self, check, now=long(time.time())):
		maxtimediff = self.options.get('seconds') or 86400
		markold = self.options.get('markold') or False

		timedelta = now - long(check['timestamp'])
		if timedelta > maxtimediff:
			check['output'] = 'Nag(ix)SC: Check result is %s(>%s) seconds old - %s' % (timedelta, maxtimediff, check['output'])
			if markold:
				check['returncode'] = 3
		return check


	def read_xml(self):
		if self.options.get('url') != None:
			request = urllib2.Request(self.options['url'])

			if self.options.get('httpuser') and self.options.get('httppasswd'):
				if self.options.get('httpforceauth'):
					request.add_header('Authorization', 'Basic ' + base64.b64encode(self.options['httpuser'] + ':' + self.options['httppasswd']))
				else:
					passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
					passman.add_password(None, self.options['url'], self.options['httpuser'], self.options['httppasswd'])
					authhandler = urllib2.HTTPBasicAuthHandler(passman)
					opener = urllib2.build_opener(authhandler)
					urllib2.install_opener(opener)

			try:
				response = urllib2.urlopen(request)
			except urllib2.HTTPError, error:
				return (False, error)
			except urllib2.URLError, error:
				return (False, error)

			self.xmldoc = ET.parse(response)
			response.close()

			return (True, 'XML loaded from URL "%s"' % self.options['url'])

		elif self.options.get('file'):
			if self.options['file'] == '-':
				self.options['file'] = sys.stdin
			try:
				self.xmldoc = ET.parse(self.options['file'])
			except IOError, error:
				return (False, error)

			if type(self.options['file'] == file):
				filename = self.options['file'].name
			return (True, 'XML loaded from file "%s"' % filename)

		else:
			return (False, 'Neither URL nor file specified!')


	def read_xml_from_string(self, content):
		self.xmldoc = ET.parsestring(content)
		return True


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


	def dict2out_passive(self):
		FORMAT_HOST = '[%s] PROCESS_HOST_CHECK_RESULT;%s;%s;%s'
		FORMAT_SERVICE = '[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%s;%s'
		count_services = 0
		now = str(long(time.time()))

		# Prepare pipe
		if self.options['verbose'] <= 2:
			try:
				pipe = open(self.options['pipe'], "w")
			except IOError, error:
				return (False, count_services, error)
		else:
			pipe = None

		# Output
		for check in self.checks:
			count_services += 1
			if check.has_key('timestamp'):
				timestamp = check['timestamp']
			else:
				timestamp = self.xmltimestamp or now

			if check['service_description'] in ['', None,]:
				# Host check
				line = FORMAT_HOST % (timestamp, check['host_name'], check['returncode'], check['output'].replace('\n', '\\n'))
			else:
				# Service check
				line =  FORMAT_SERVICE % (timestamp, check['host_name'], check['service_description'], check['returncode'], check['output'].replace('\n', '\\n'))

			if pipe:
				pipe.write(line + '\n')
			self.debug(2, line)

		# Close
		if pipe:
			pipe.close()
		else:
			self.debug(2, "Passive check results NOT written to Nagios/Icinga command pipe due to -vvv!")

		return (True, count_services, 'Written %s check result(s) to command pipe' % count_services)


	def dict2out_checkresult(self):
		count_services = 0
		count_failed = 0
		list_failed = []
		chars = string.letters + string.digits
		ctimestamp = time.ctime()
		random.seed()
		now = str(long(time.time()))

		for check in self.checks:
			count_services += 1
			timestamp = check.get('timestamp') or now

			filename = os.path.join(self.options['checkresultdir'], 'c' + ''.join([random.choice(chars) for i in range(6)]))
			while os.path.exists(filename):
				filename = os.path.join(self.options['checkresultdir'], 'c' + ''.join([random.choice(chars) for i in range(6)]))

			try:
				crfile = open(filename, "w")
				if check['service_description'] in ['', None,]:
					# Host check - FIXME passive Check
					crfile.write('### Active Check Result File ###\nfile_time=%s\n\n### Nagios Service Check Result ###\n# Time: %s\nhost_name=%s\ncheck_type=0\ncheck_options=0\nscheduled_check=1\nreschedule_check=1\nlatency=0.0\nstart_time=%s.00\nfinish_time=%s.05\nearly_timeout=0\nexited_ok=1\nreturn_code=%s\noutput=%s\n' % (timestamp, ctimestamp, check['host_name'], timestamp, timestamp, check['returncode'], check['output'].replace('\n', '\\n') ) )
				else:
					# Service check - FIXME passive Check
					crfile.write('### Active Check Result File ###\nfile_time=%s\n\n### Nagios Service Check Result ###\n# Time: %s\nhost_name=%s\nservice_description=%s\ncheck_type=0\ncheck_options=0\nscheduled_check=1\nreschedule_check=1\nlatency=0.0\nstart_time=%s.00\nfinish_time=%s.05\nearly_timeout=0\nexited_ok=1\nreturn_code=%s\noutput=%s\n' % (timestamp, ctimestamp, check['host_name'], check['service_description'], timestamp, timestamp, check['returncode'], check['output'].replace('\n', '\\n') ) )
				crfile.close()

				# Create OK file
				open(filename + '.ok', 'w').close()
			except:
				count_failed += 1
				list_failed.append([filename, check['host_name'], check['service_description']])

		return (True, count_services, count_failed, list_failed)


	def xml_check_version(self):
		if not self.xmldoc:
			return (False, 'No XML structure loaded')

		# FIXME: Check XML structure
		try:
			xmlnagixsc = self.xmldoc.getroot()
		except:
			return (False, 'Not a Nag(ix)SC XML file!')

		if not xmlnagixsc.attrib.get('version'):
			return (False, 'No version information found in XML file!')

		version = xmlnagixsc.attrib['version']
		if not version.startswith('1.'):
			return (False, 'Not a Nag(ix)SC XML 1.X file')

		return (True, 'XML seems to be ok')


	def xml_get_timestamp(self):
		xmlroot = self.xmldoc.getroot()

		if not xmlroot:
			return (False, 'Could not find XML root node')

		xmltimestamps = xmlroot.findall('timestamp')

		if len(xmltimestamps) != 1:
			return (False, 'Found %s instead of one timestamp in XML' % len(xmltimestamps))

		try:
			timestamp = long(xmltimestamps[0].text)
		except ValueError:
			return (False, 'Timestamp is wrong: "%s"' % xmltimestamp.text)

		self.xmltimestamp = timestamp
		return (True, timestamp)


	def xml_to_dict(self):
		if not self.xmltimestamp:
			(status, response) = self.xml_get_timestamp()
			if not status:
				print response
				sys.exit(2)

		self.xmltimestamp = self.reset_future_timestamp(self.xmltimestamp)

		for xmlhost in self.xmldoc.getroot().findall('host'):
			xmlhostname = xmlhost.find('name')
			hostname = self.decode(xmlhostname.text, xmlhostname.attrib.get('encoding'))
			self.debug(2, 'Found host "%s"' % hostname)

			# Hostfilter?
			if self.options.get('hostfilter') and self.options['hostfilter'] != hostname:
				continue

			# Service filter? Dont look for host check
			if not self.options.get('servicefilter'):

				# Look for Host check result
				xmlreturncode = xmlhost.find('returncode')
				if xmlreturncode is not None:
					returncode = xmlreturncode.text
				else:
					returncode = None

				xmloutput = xmlhost.find('output')
				if xmloutput is not None:
					output = self.decode(xmloutput.text, xmloutput.attrib.get('encoding'))
				else:
					output = None

				xmltimestamp = xmlhost.find('timestamp')
				if xmltimestamp is not None:
					timestamp = self.reset_future_timestamp(xmltimestamp.text)
				else:
					timestamp = self.xmltimestamp

				# Append only if returncode and output are set
				if returncode and output:
					self.checks.append({'host_name':hostname, 'service_description':None, 'returncode':returncode, 'output':output, 'timestamp':timestamp})
					self.debug(1, 'Host: "%s" - RetCode: "%s" - Output: "%s"' % (hostname, returncode, output) )

			# Loop over services in host
			for xmlservice in xmlhost.findall('service'):
				service_dict = {}

				xmlsrvdescr = xmlservice.find('description')
				srvdescr = self.decode(xmlsrvdescr.text, xmlsrvdescr.attrib.get('encoding'))

				if self.options.get('servicefilter') and self.options['servicefilter'] != srvdescr:
					continue

				xmlreturncode = xmlservice.find('returncode')
				returncode = xmlreturncode.text

				xmloutput = xmlservice.find('output')
				output = self.decode(xmloutput.text, xmloutput.attrib.get('encoding'))

				xmltimestamp = xmlservice.find('timestamp')
				if xmltimestamp is not None:
					timestamp = self.reset_future_timestamp(xmltimestamp.text)
				else:
					timestamp = self.xmltimestamp

				self.debug(2, 'Found service "%s"' % srvdescr)

				service_dict = {'host_name':hostname, 'service_description':srvdescr, 'returncode':returncode, 'output':output, 'timestamp':timestamp}
				self.checks.append(service_dict)

				self.debug(1, 'Host: "%s" - Service: "%s" - RetCode: "%s" - Output: "%s"' % (hostname, srvdescr, returncode, output) )


	def xml_from_dict(self):
		self.encoding = self.options.get('encoding') or 'base64'

		lasthost = None

		db = [(check['host_name'], check) for check in self.checks]
		db.sort()

		xmlroot = ET.Element('nagixsc')
		xmlroot.set('version', '1.0')
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


