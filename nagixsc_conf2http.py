#!/usr/bin/python

import BaseHTTPServer
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

	config['conf_dir']         = cfgread.get('server', 'conf_dir')
	config['conf2xml_cmdline'] = cfgread.get('server', 'conf2xml_cmdline')

except ConfigParser.NoOptionError, e:
	print 'Config file error: %s ' % e
	sys.exit(1)

users = {}
for u in cfgread.options('users'):
	users[u] = cfgread.get('users', u)

##############################################################################

class Conf2HTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):

	def http_error(self, code, output):
		self.send_response(code)
		self.send_header('Content-Type', 'text/plain')
		self.end_headers()
		self.wfile.write(output)
		return


	def do_GET(self):
		cmdline = config['conf2xml_cmdline']

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
			service = ''

		if len(path) >= 3:
			host = path[2]
		else:
			host = ''

		if len(path) >= 2:
			configfile = path[1]
		else:
			configfile =''

		if re.search('\.\.', configfile):
			self.http_error(500, 'Found ".." in config file name')
			return
		if configfile and not re.search('^[a-zA-Z0-9-_\.]+$', configfile):
			self.http_error(500, 'Config file name contains invalid characters')
			return

		if configfile:
			configfile += '.conf'
			cmdline    += ' -c ' + os.path.join(config['conf_dir'], configfile)

		if host:
			cmdline += ' -H %s' % host
			if service:
				cmdline += ' -D %s' % service

		try:
			cmd     = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE)
			output  = cmd.communicate()[0].rstrip()
			retcode = cmd.returncode
		except OSError:
			self.http_error(500, 'Could not execute "%s"' % cmdline)
			return

		if retcode == 0:
			self.send_response(200)
			self.send_header('Content-Type', 'text/xml')
			self.end_headers()
			self.wfile.write(output)
		else:
			self.http_error(500, output)

		return



def main():
	try:
		server = BaseHTTPServer.HTTPServer((config['ip'], config['port']), Conf2HTTPHandler)
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	main()

