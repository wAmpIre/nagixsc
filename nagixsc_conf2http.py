#!/usr/bin/python

import BaseHTTPServer
import base64
import md5
import os
import re
import subprocess

config = {	'ip':			'',
			'port':			15666,
		}

users = {	'nagixsc':		'019b0966d98fb71d1a4bc4ca0c81d5cc',		# PW: nagixsc
		}

CONFDIR='./examples'
C2X='./nagixsc_conf2xml.py'

class Conf2HTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):

	def http_error(code, output):
		self.send_response(code)
		self.send_header('Content-Type', 'text/plain')
		self.end_headers()
		self.wfile.write(output)
		return


	def do_GET(self):
		cmdline = C2X

		path = self.path.split('/')

		# Check Basic Auth
		try:
			authdata = base64.b64decode(self.headers['Authorization'].split(' ')[1]).split(':')
			if not users[authdata[0]] == md5.md5(authdata[1]).hexdigest():
				raise Exception
		except:
			self.send_response(401)
			self.send_header('WWW-Authenticate', 'Basic realm="Nag(ix)SC"')
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
			http_error(500, 'Found ".." in config file name')
			return
		if configfile and not re.search('^[a-zA-Z0-9-_\.]+$', configfile):
			http_error(500, 'Config file name contains invalid characters')
			return

		if configfile:
			configfile += '.conf'
			cmdline    += ' -c ' + os.path.join(CONFDIR, configfile)

		if host:
			cmdline += ' -H %s' % host
			if service:
				cmdline += ' -D %s' % service

		try:
			cmd     = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE)
			output  = cmd.communicate()[0].rstrip()
			retcode = cmd.returncode
		except OSError:
			http_error(500, 'Could not execute "%s"' % cmdline)
			return

		if retcode == 0:
			self.send_response(200)
			self.send_header('Content-Type', 'text/xml')
			self.end_headers()
			self.wfile.write(output)
		else:
			http_error(500, output)

		return



def main():
	try:
		server = BaseHTTPServer.HTTPServer((config['ip'], config['port']), Conf2HTTPHandler)
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	main()

