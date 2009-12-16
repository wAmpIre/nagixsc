#!/usr/bin/python

import BaseHTTPServer
import base64
import cgi
import os
import re
import subprocess

try:
	from hashlib import md5
except ImportError:
	from md5 import md5

config = {	'ip':			'',
			'port':			15667,
		}

users = {	'nagixsc':		'019b0966d98fb71d1a4bc4ca0c81d5cc',		# PW: nagixsc
		}

XMLFILESIZE=102400
X2N='./nagixsc_xml2nagios.py -O passive -vvv -f -'

class HTTP2NagiosHandler(BaseHTTPServer.BaseHTTPRequestHandler):

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
		cmdline = X2N

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
			try:
				cmd     = subprocess.Popen(cmdline.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
				output  = cmd.communicate(xmltext)[0].rstrip()
				retcode = cmd.returncode

				if retcode == 0:
					self.send_response(200)
					self.send_header('Content-Type', 'text/plain')
					self.end_headers()
					self.wfile.write(output)
					return
				else:
					http_error(500, output)
					return

			except OSError:
				http_error(500, 'Nag(IX)SC - Could not execute "%s"' % cmdline)
				return

		else:
			http_error(500, 'Nag(IX)SC - No data received')
			return



def main():
	try:
		server = BaseHTTPServer.HTTPServer((config['ip'], config['port']), HTTP2NagiosHandler)
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	print 'curl -v -u nagixsc:nagixsc -F \'xmlfile=@xml/nagixsc.xml\' http://127.0.0.1:15667/\n\n'
	main()

