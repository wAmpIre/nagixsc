#!/usr/bin/python

import ConfigParser
import base64
import optparse
import os
import re
import subprocess
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

parser.set_defaults(cfgfile='conf2http.cfg')

(options, args) = parser.parse_args()

cfgread = ConfigParser.SafeConfigParser()
cfgread.optionxform = str # We need case-sensitive options
cfg_list = cfgread.read(options.cfgfile)

if cfg_list == []:
	print 'Config file "%s" could not be read!' % options.cfgfile
	sys.exit(1)

config = {
			'ip': '0.0.0.0',
			'port': '15666',
			'ssl': False,
			'sslcert': None,
			'conf_dir': '',
			'pidfile': '/var/run/nagixsc_conf2http.pid',
			'livestatus_socket' : None,
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
		print 'Value for "ssl" ("%s") not boolean!' % config['ssl']
		sys.exit(127)

if config['ssl']:
	if 'sslcert' in cfgread.options('server'):
		config['sslcert'] = cfgread.get('server', 'sslcert')
	else:
		print 'SSL but no certificate file specified!'
		sys.exit(127)

try:
	config['conf_dir'] = cfgread.get('server', 'conf_dir')
except ConfigParser.NoOptionError:
	print 'No "conf_dir" specified!'
	sys.exit(127)

if 'pidfile' in cfgread.options('server'):
	config['pidfile'] = cfgread.get('server', 'pidfile')

if 'livestatus_socket' in cfgread.options('server'):
	config['livestatus_socket'] = prepare_socket(cfgread.get('server', 'livestatus_socket'))


users = {}
for u in cfgread.options('users'):
	users[u] = cfgread.get('users', u)

##############################################################################

class Conf2HTTPHandler(MyHTTPRequestHandler):

	def http_error(self, code, output):
		self.send_response(code)
		self.send_header('Content-Type', 'text/plain')
		self.end_headers()
		self.wfile.write(output)
		return


	def do_GET(self):
		path = self.path.split('/')

		# Check Basic Auth
		try:
			authdata = base64.b64decode(self.headers['Authorization'].split(' ')[1]).split(':')
			if not users[authdata[0]] == md5(authdata[1]).hexdigest():
				raise Exception
		except:
			self.send_response(401)
			self.send_header('WWW-Authenticate', 'Basic realm="Nag(ix)SC Pull"')
			self.send_header('Content-Type', 'text/plain')
			self.end_headers()
			self.wfile.write('Sorry! No action without login!')
			return


		if len(path) >= 4:
			service = path[3]
		else:
			service = None

		if len(path) >= 3:
			host = path[2]
		else:
			host = None

		if len(path) >= 2:
			configfile = path[1] + '.conf'
		else:
			self.http_error(500, 'No config file specified')
			return

		if re.search('\.\.', configfile):
			self.http_error(500, 'Found ".." in config file name')
			return
		if not re.search('^[a-zA-Z0-9-_]+.conf$', configfile):
			self.http_error(500, 'Config file name contains invalid characters')
			return

		# Just be sure it exists
		checks = None

		# If config file name starts with "_" it's something special
		if not configfile.startswith('_'):
			# Try to read config file, execute checks
			check_config = read_inifile(os.path.join(config['conf_dir'], configfile))
			if not check_config:
				self.http_error(500, 'Could not read config file "%s"' % configfile)
				return
			checks = conf2dict(check_config, host, service)

		elif configfile=='_livestatus.conf' and config['livestatus_socket']:
			# Read mk-livestatus and translate into XML
			checks = livestatus2dict(config['livestatus_socket'], host, service)


		# No check results? No (good) answer...
		if not checks:
			self.http_error(500, 'No check results')
			return

		self.send_response(200)
		self.send_header('Content-Type', 'text/xml')
		self.end_headers()
		self.wfile.write(xml_from_dict(checks))

		return



def main():
	if options.nossl:
		config['ssl'] = False

	if config['ssl'] and not os.path.isfile(config['sslcert']):
		print 'SSL certificate "%s" not found!' % config['sslcert']
		sys.exit(127)

	if not os.path.isdir(config['conf_dir']):
		print 'Not a config file directory: "%s"' % config['conf_dir']
		sys.exit(127)

	if options.daemon:
		daemonize(pidfile=config['pidfile'])

	server = MyHTTPServer((config['ip'], config['port']), Conf2HTTPHandler, ssl=config['ssl'], sslpemfile=config['sslcert'])
	try:
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	main()

