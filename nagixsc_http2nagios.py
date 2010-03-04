#!/usr/bin/python

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

config = {}
try:
	config['ip']   = cfgread.get('server', 'ip')
	config['port'] = cfgread.getint('server', 'port')
	config['ssl']  = cfgread.getboolean('server', 'ssl')
	config['cert'] = cfgread.get('server', 'sslcert')

	config['max_xml_file_size']  = cfgread.get('server', 'max_xml_file_size')
	config['checkresultdir'] = cfgread.get('mode_checkresult', 'dir')

except ConfigParser.NoOptionError, e:
	print 'Config file error: %s ' % e
	sys.exit(1)

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

			(count_services, count_failed, list_failed) = dict2out_checkresult(checks, xml_get_timestamp(doc), config['checkresultdir'], 0)

			if count_failed < count_services:
				self.send_response(200)
				self.send_header('Content-Type', 'text/plain')
				self.end_headers()
				self.wfile.write('Wrote %s check results, %s failed' % (count_services, count_failed))
				return
			else:
				self.http_error(501, 'Could not write all %s check results' % count_services)
				return

		else:
			self.http_error(502, 'Nag(IX)SC - No data received')
			return



def main():
	if options.nossl:
		config['ssl'] = False

	if config['ssl'] and not os.path.isfile(config['cert']):
		print 'SSL certificate "%s" not found!' % config['cert']
		sys.exit(127)

	if options.daemon:
		daemonize(pidfile='/var/run/nagixsc_http2nagios.pid')

	server = MyHTTPServer((config['ip'], config['port']), HTTP2NagiosHandler, ssl=config['ssl'], sslpemfile=config['cert'])
	try:
		server.serve_forever()
	except:
		server.socket.close()

if __name__ == '__main__':
	print 'curl -v -u nagixsc:nagixsc -F \'xmlfile=@xml/nagixsc.xml\' http://127.0.0.1:15667/\n\n'
	main()

