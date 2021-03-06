#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_http2nagios.py
#
# Copyright (C) 2009-2010 Sven Velt <sv@teamix.net>
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
import cgi
import optparse
import os
import re
import sys

try:
	from hashlib import md5
except ImportError:
	from md5 import md5

##############################################################################

from nagixsc import *

##############################################################################

parser = optparse.OptionParser()

parser.add_option('-c', '', dest='cfgfile', help='Config file')
parser.add_option('-d', '--daemon', action='store_true', dest='daemon', help='Daemonize, go to background')
parser.add_option('', '--nossl', action='store_true', dest='nossl', help='Disable SSL (overwrites config file)')

parser.set_defaults(cfgfile='http2nagios.cfg')

(options, args) = parser.parse_args()

cfgread = ConfigParser.SafeConfigParser()
cfgread.optionxform = str # We need case-sensitive options
cfg_list = cfgread.read(options.cfgfile)

if cfg_list == []:
	print 'Config file "%s" could not be read!' % options.cfgfile
	sys.exit(1)

config = {
			'ip': '0.0.0.0',
			'port': '15667',
			'ssl': False,
			'sslcert': None,
			'conf_dir': '',
			'pidfile': '/var/run/nagixsc_conf2http.pid',
			'acl': False,
		}

if 'ip' in cfgread.options('server'):
	config['ip'] = cfgread.get('server', 'ip')

if 'port' in cfgread.options('server'):
	config['port'] = cfgread.get('server', 'port')
try:
	config['port'] = int(config['port'])
except ValueError:
	print 'Port "%s" not an integer!' % config['port']
	sys.exit(127)

if 'ssl' in cfgread.options('server'):
	try:
		config['ssl'] = cfgread.getboolean('server', 'ssl')
	except ValueError:
		print 'Value for "ssl" ("%s") not boolean!' % cfgread.get('server', 'ssl')
		sys.exit(127)

if config['ssl']:
	if 'sslcert' in cfgread.options('server'):
		config['sslcert'] = cfgread.get('server', 'sslcert')
	else:
		print 'SSL but no certificate file specified!'
		sys.exit(127)

try:
	config['mode'] = cfgread.get('server', 'mode')
except ConfigParser.NoOptionError:
	print 'No "mode" specified!'
	sys.exit(127)

if config['mode']=='checkresult':
	try:
		config['checkresultdir'] = cfgread.get('mode_checkresult','dir')
	except ConfigParser.NoOptionError:
		print 'No "dir" in section "mode_checkresult" specified!'
		sys.exit(127)

	if os.access(config['checkresultdir'],os.W_OK) == False:
		print 'Checkresult directory "%s" is not writable!' % config['checkresultdir']
		sys.exit(1)

elif config['mode']=='passive':
	try:
		config['pipe'] = cfgread.get('mode_passive','pipe')
	except ConfigParser.NoOptionError:
		print 'No "pipe" in section "mode_passive" specified!'
		sys.exit(127)

	if os.access(config['pipe'],os.W_OK) == False:
		print 'Nagios command pipe "%s" is not writable!' % config['pipe']
		sys.exit(1)

else:
	print 'Mode "%s" is neither "checkresult" nor "passive"!'
	sys.exit(127)

acls = { 'a_hl':{}, 'a_hr':{}, }
if 'acl' in cfgread.options('server'):
	try:
		config['acl'] = cfgread.getboolean('server', 'acl')
	except ValueError:
		print 'Value for "acl" ("%s") not boolean!' % cfgread.get('server', 'acl')
		sys.exit(127)
if config['acl']:
	if cfgread.has_section('acl_allowed_hosts_list'):
		for user in cfgread.options('acl_allowed_hosts_list'):
			acls['a_hl'][user] = [ah.lstrip().rstrip() for ah in cfgread.get('acl_allowed_hosts_list',user).split(',')]
	if cfgread.has_section('acl_allowed_hosts_re'):
		for user in cfgread.options('acl_allowed_hosts_re'):
			acls['a_hr'][user] = re.compile(cfgread.get('acl_allowed_hosts_re',user))



users = {}
for u in cfgread.options('users'):
	users[u] = cfgread.get('users', u)

##############################################################################

class HTTP2NagiosHandler(MyHTTPRequestHandler):

	def http_error(self, code, output):
		self.send_response(code)
		self.send_header('Content-Type', 'text/plain')
		self.end_headers()
		self.wfile.write(output)
		return


	def do_GET(self):
		self.send_response(200)
		self.send_header('Content-Type', 'text/html')
		self.end_headers()
		self.wfile.write('''			<html><body>
				<form action="." method="post" enctype="multipart/form-data">
				filename: <input type="file" name="xmlfile" /><br />
				<input type="submit" />
				</form>
			</body></html>
			''')
		return


	def do_POST(self):
		# Check Basic Auth
		try:
			authdata = base64.b64decode(self.headers['Authorization'].split(' ')[1]).split(':')
			if not users[authdata[0]] == md5(authdata[1]).hexdigest():
				raise Exception
		except:
			self.send_response(401)
			self.send_header('WWW-Authenticate', 'Basic realm="Nag(ix)SC HTTP Push"')
			self.send_header('Content-Type', 'text/plain')
			self.end_headers()
			self.wfile.write('Sorry! No action without login!')
			return

		(ctype,pdict) = cgi.parse_header(self.headers.getheader('content-type'))
		if ctype == 'multipart/form-data':
			query = cgi.parse_multipart(self.rfile, pdict)
		xmltext = query.get('xmlfile')[0]

		if len(xmltext) > 0:
			doc = read_xml_from_string(xmltext)
			checks = xml_to_dict(doc)

			if config['acl']:
				new_checks = []
				for check in checks:
					if authdata[0] in acls['a_hl'] and check['host_name'] in acls['a_hl'][authdata[0]]:
						new_checks.append(check)
					elif authdata[0] in acls['a_hr'] and (acls['a_hr'][authdata[0]]).search(check['host_name']):
						new_checks.append(check)

				count_acl_failed = len(checks) - len(new_checks)
				checks = new_checks
			else:
				count_acl_failed = None

			if config['mode'] == 'checkresult':
				(count_services, count_failed, list_failed) = dict2out_checkresult(checks, xml_get_timestamp(doc), config['checkresultdir'])

				if count_failed < count_services:
					self.send_response(200)
					self.send_header('Content-Type', 'text/plain')
					self.end_headers()
					statusmsg = 'Wrote %s check results, %s failed' % (count_services, count_failed)
					if count_acl_failed != None:
						statusmsg += ' - %s check results failed ACL check' % count_acl_failed
					self.wfile.write(statusmsg)
					return
				else:
					self.http_error(501, 'Could not write all %s check results' % count_services)
					return

			elif config['mode'] == 'passive':
				count_services = dict2out_passive(checks, xml_get_timestamp(doc), config['pipe'])

				self.send_response(200)
				self.send_header('Content-Type', 'text/plain')
				self.end_headers()
				self.wfile.write('Wrote %s check results' % count_services)
				return

		else:
			self.http_error(502, 'Nag(IX)SC - No data received')
			return



def main():
	if options.nossl:
		config['ssl'] = False

	if config['ssl'] and not os.path.isfile(config['sslcert']):
		print 'SSL certificate "%s" not found!' % config['sslcert']
		sys.exit(127)

	if options.daemon:
		daemonize(pidfile=config['pidfile'])
	else:
		print 'curl -v -u nagixsc:nagixsc -F \'xmlfile=@xml/nagixsc.xml\' http://127.0.0.1:%s/\n\n' % config['port']

	server = MyHTTPServer((config['ip'], config['port']), HTTP2NagiosHandler, ssl=config['ssl'], sslpemfile=config['sslcert'])
	try:
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	main()

