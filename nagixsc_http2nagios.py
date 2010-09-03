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

config = {
			'ip': '0.0.0.0',
			'port': '15666',
			'ssl': False,
			'sslcert': None,
			'conf_dir': '',
			'pidfile': '/var/run/nagixsc_conf2http.pid'
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
		config['mode_pipe'] = cfgread.get('mode_passive','pipe')
	except ConfigParser.NoOptionError:
		print 'No "pipe" in section "mode_passive" specified!'
		sys.exit(127)

	if os.access(config['pipe'],os.W_OK) == False:
		print 'Nagios command pipe "%s" is not writable!' % config['pipe']
		sys.exit(1)

else:
	print 'Mode "%s" is neither "checkresult" nor "passive"!'
	sys.exit(127)



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

