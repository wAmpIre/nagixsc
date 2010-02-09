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

parser.set_defaults(cfgfile='conf2http.cfg')

(options, args) = parser.parse_args()

cfgread = ConfigParser.SafeConfigParser()
cfgread.optionxform = str # We need case-sensitive options
cfg_list = cfgread.read(options.cfgfile)

if cfg_list == []:
	print 'Config file "%s" could not be read!' % options.cfgfile
	sys.exit(1)

config = {}
try:
	config['ip']   = cfgread.get('server', 'ip')
	config['port'] = cfgread.getint('server', 'port')
	config['ssl']  = cfgread.getboolean('server', 'ssl')
	config['cert'] = cfgread.get('server', 'sslcert')

	config['conf_dir']         = cfgread.get('server', 'conf_dir')

except ConfigParser.NoOptionError, e:
	print 'Config file error: %s ' % e
	sys.exit(1)

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
		if not re.search('^[a-zA-Z0-9-_\.]+$', configfile):
			self.http_error(500, 'Config file name contains invalid characters')
			return

		check_config = read_inifile(os.path.join(config['conf_dir'], configfile))
		if not check_config:
			self.http_error(500, 'Could not read config file "%s"' % configfile)
			return

		checks = conf2dict(check_config, host, service)
		if not checks:
			self.http_error(500, 'No checks executed')
			return

		self.send_response(200)
		self.send_header('Content-Type', 'text/xml')
		self.end_headers()
		self.wfile.write(xml_from_dict(checks))

		return



def main():
	if config['ssl'] and not os.path.isfile(config['cert']):
		print 'SSL certificate "%s" not found!' % config['cert']
		sys.exit(127)

	server = MyHTTPServer((config['ip'], config['port']), Conf2HTTPHandler, ssl=config['ssl'], sslpemfile=config['cert'])
	try:
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	main()

