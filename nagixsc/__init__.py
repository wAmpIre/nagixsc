import BaseHTTPServer
import ConfigParser
import SocketServer
import base64
import datetime
import libxml2
import mimetools
import os
import random
import shlex
import signal
import socket
import string
import subprocess
import sys

def debug(level, verb, string):
	if level <= verb:
		print "%s: %s" % (level, string)


##############################################################################

class ExecTimeoutError(Exception):
	pass

##############################################################################

def available_encodings():
	return ['base64', 'plain',]


def check_encoding(enc):
	if enc in available_encodings():
		return True
	else:
		return False


def decode(data, encoding):
	if encoding == 'plain':
		return data
	else:
		return base64.b64decode(data)


def encode(data, encoding=None):
	if encoding == 'plain':
		return data
	else:
		return base64.b64encode(data)


##############################################################################

def read_inifile(inifile):
	config = ConfigParser.RawConfigParser()
	config.optionxform = str # We need case-sensitive options
	ini_list = config.read(inifile)

	if ini_list:
		return config
	else:
		return False


##############################################################################

def exec_timeout_handler(signum, frame):
	raise ExecTimeoutError

def exec_check(host_name, service_descr, cmdline, timeout=None, timeout_returncode=2):
	cmdarray = shlex.split(cmdline)

	check = {}
	check['host_name'] = host_name
	check['service_description'] = service_descr

	if len(cmdarray) == 0:
		check['output'] = 'No command line specified!'
		check['returncode'] = 127
		return check

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

	check['timestamp'] = datetime.datetime.now().strftime('%s')
	return check


##############################################################################

def conf2dict(config, opt_host=None, opt_service=None):
	checks = []

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

	# Sections are Hosts (not 'nagixsc'), options in sections are Services
	hosts = config.sections()
	if 'nagixsc' in hosts:
		hosts.remove('nagixsc')

	# Filter out host/section if it exists
	if opt_host:
		if opt_host in hosts:
			hosts = [opt_host,]
		else:
			hosts = []

	for host in hosts:
		# Overwrite section/host name with '_host_name'
		if config.has_option(host,'_host_name'):
			host_name = config.get(host,'_host_name')
		else:
			host_name = host


		services = config.options(host)
		# Look for host check
		if '_host_check' in services and not opt_service:
			cmdline = config.get(host, '_host_check')
			check = exec_check(host_name, None, cmdline, timeout, timeout_returncode)
			checks.append(check)


		# Filter out service if given in cmd line options
		if opt_service:
			if opt_service in services:
				services = [opt_service,]
			else:
				services = []

		for service in services:
			# If option starts with '_' it may be a NagixSC option in the future
			if service[0] != '_':
				cmdline = config.get(host, service)

				check = exec_check(host_name, service, cmdline, timeout, timeout_returncode)
				checks.append(check)

	return checks


##############################################################################

def dict2out_passive(checks, xmltimestamp, opt_pipe, opt_verb=0):
	FORMAT_HOST = '[%s] PROCESS_HOST_CHECK_RESULT;%s;%s;%s'
	FORMAT_SERVICE = '[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%s;%s'
	count_services = 0
	now = datetime.datetime.now().strftime('%s')

	# Prepare
	if opt_verb <= 2:
		pipe = open(opt_pipe, "w")
	else:
		pipe = None

	# Output
	for check in checks:
		count_services += 1
		if check.has_key('timestamp'):
			timestamp = check['timestamp']
		else:
			timestamp = xmltimestamp
		count_services += 1

		if check['service_description'] == None or check['service_description'] == '':
			# Host check
			line = FORMAT_HOST % (now, check['host_name'], check['returncode'], check['output'].replace('\n', '\\n'))
		else:
			# Service check
			line =  FORMAT_SERVICE % (now, check['host_name'], check['service_description'], check['returncode'], check['output'].replace('\n', '\\n'))

		if pipe:
			pipe.write(line + '\n')
		debug(2, opt_verb, line)

	# Close
	if pipe:
		pipe.close()
	else:
		print "Passive check results NOT written to Nagios pipe due to -vvv!"

	return count_services


def dict2out_checkresult(checks, xmltimestamp, opt_checkresultdir, opt_verb):
	count_services = 0
	count_failed = 0
	list_failed = []
	chars = string.letters + string.digits
	ctimestamp = datetime.datetime.now().ctime()

	for check in checks:
		count_services += 1
		if check.has_key('timestamp'):
			timestamp = check['timestamp']
		else:
			timestamp = xmltimestamp

		filename = os.path.join(opt_checkresultdir, 'c' + ''.join([random.choice(chars) for i in range(6)]))
		try:
			crfile = open(filename, "w")
			if check['service_description'] == None or check['service_description'] == '':
				# Host check
				crfile.write('### Active Check Result File ###\nfile_time=%s\n\n### Nagios Service Check Result ###\n# Time: %s\nhost_name=%s\ncheck_type=0\ncheck_options=0\nscheduled_check=1\nreschedule_check=1\nlatency=0.0\nstart_time=%s.00\nfinish_time=%s.05\nearly_timeout=0\nexited_ok=1\nreturn_code=%s\noutput=%s\n' % (timestamp, ctimestamp, check['host_name'], timestamp, timestamp, check['returncode'], check['output'].replace('\n', '\\n') ) )
			else:
				# Service check
				crfile.write('### Active Check Result File ###\nfile_time=%s\n\n### Nagios Service Check Result ###\n# Time: %s\nhost_name=%s\nservice_description=%s\ncheck_type=0\ncheck_options=0\nscheduled_check=1\nreschedule_check=1\nlatency=0.0\nstart_time=%s.00\nfinish_time=%s.05\nearly_timeout=0\nexited_ok=1\nreturn_code=%s\noutput=%s\n' % (timestamp, ctimestamp, check['host_name'], check['service_description'], timestamp, timestamp, check['returncode'], check['output'].replace('\n', '\\n') ) )
			crfile.close()

			# Create OK file
			open(filename + '.ok', 'w').close()
		except:
			count_failed += 1
			list_failed.append([filename, check['host_name'], check['service_description']])

	return (count_services, count_failed, list_failed)


##############################################################################

def read_xml(options):
	if options.url != None:
		import urllib2

		if options.httpuser and options.httppasswd:
			passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
			passman.add_password(None, options.url, options.httpuser, options.httppasswd)
			authhandler = urllib2.HTTPBasicAuthHandler(passman)
			opener = urllib2.build_opener(authhandler)
			urllib2.install_opener(opener)

		try:
			response = urllib2.urlopen(options.url)
		except urllib2.HTTPError, error:
			print error
			sys.exit(0)
		except urllib2.URLError, error:
			print error.reason[1]
			sys.exit(0)

		doc = libxml2.parseDoc(response.read())
		response.close()

	else:
		doc = libxml2.parseFile(options.file)

	return doc


def read_xml_from_string(content):
	return libxml2.parseDoc(content)


##############################################################################

def xml_check_version(xmldoc):
	# FIXME: Check XML structure
	try:
		xmlnagixsc = xmldoc.xpathNewContext().xpathEval('/nagixsc')[0]
	except:
		return (False, 'Not a Nag(IX)SC XML file!')

	try:
		if xmlnagixsc.prop('version') != "1.0":
			return (False, 'Wrong version (found "%s", need "1.0") of XML file!' % xmlnagixsc.prop('version'))
	except:
		return (False, 'No version information found in XML file!')

	return (True, 'XML seems to be ok')


def xml_get_timestamp(xmldoc):
	try:
		timestamp = int(xmldoc.xpathNewContext().xpathEval('/nagixsc/timestamp')[0].get_content())
	except:
		return False

	return timestamp


def xml_to_dict(xmldoc, verb=0, hostfilter=None, servicefilter=None):
	checks = []
	now = int(datetime.datetime.now().strftime('%s'))
	filetimestamp = reset_future_timestamp(xml_get_timestamp(xmldoc), now)

	if hostfilter:
		hosts = xmldoc.xpathNewContext().xpathEval('/nagixsc/host[name="%s"] | /nagixsc/host[name="%s"]' % (hostfilter, encode(hostfilter)))
	else:
		hosts = xmldoc.xpathNewContext().xpathEval('/nagixsc/host')

	for host in hosts:
		xmlhostname = host.xpathEval('name')[0]
		hostname = decode(xmlhostname.get_content(), xmlhostname.prop('encoding'))
		debug(2, verb, 'Found host "%s"' % hostname)

		# Look for Host check result
		if host.xpathEval('returncode'):
			retcode   = host.xpathEval('returncode')[0].get_content()
		else:
			retcode   = None

		if host.xpathEval('output'):
			xmloutput = host.xpathEval('output')[0]
			output    = decode(xmloutput.get_content(), xmloutput.prop('encoding')).rstrip()
		else:
			output    = None

		if host.xpathEval('timestamp'):
			timestamp = reset_future_timestamp(int(host.xpathEval('timestamp')[0].get_content()), now)
		else:
			timestamp = filetimestamp

		# Append only if no service filter
		if not servicefilter and retcode and output:
			checks.append({'host_name':hostname, 'service_description':None, 'returncode':retcode, 'output':output, 'timestamp':timestamp})


		# Look for service filter
		if servicefilter:
			services = host.xpathEval('service[description="%s"] | service[description="%s"]' % (servicefilter, encode(servicefilter)))
		else:
			services = host.xpathEval('service')

		# Loop over services in host
		for service in services:
			service_dict = {}

			xmldescr  = service.xpathEval('description')[0]
			xmloutput = service.xpathEval('output')[0]

			srvdescr = decode(xmldescr.get_content(), xmldescr.prop('encoding'))
			retcode  = service.xpathEval('returncode')[0].get_content()
			output   = decode(xmloutput.get_content(), xmloutput.prop('encoding')).rstrip()

			try:
				timestamp = reset_future_timestamp(int(service.xpathEval('timestamp')[0].get_content()), now)
			except:
				timestamp = filetimestamp

			debug(2, verb, 'Found service "%s"' % srvdescr)

			service_dict = {'host_name':hostname, 'service_description':srvdescr, 'returncode':retcode, 'output':output, 'timestamp':timestamp}
			checks.append(service_dict)

			debug(1, verb, 'Host: "%s" - Service: "%s" - RetCode: "%s" - Output: "%s"' % (hostname, srvdescr, retcode, output) )

	return checks


def xml_from_dict(checks, encoding='base64'):
	lasthost = None

	db = [(check['host_name'], check) for check in checks]
	db.sort()

	xmldoc = libxml2.newDoc('1.0')
	xmlroot = xmldoc.newChild(None, 'nagixsc', None)
	xmlroot.setProp('version', '1.0')
	xmltimestamp = xmlroot.newChild(None, 'timestamp', datetime.datetime.now().strftime('%s'))

	for entry in db:
		check = entry[1]

		if check['host_name'] != lasthost:
			xmlhost = xmlroot.newChild(None, 'host', None)
			xmlhostname = xmlhost.newChild(None, 'name', encode(check['host_name'], encoding))
			lasthost = check['host_name']

		if check['service_description'] == '' or check['service_description'] == None:
			# Host check result
			xmlreturncode = xmlhost.newChild(None, 'returncode', str(check['returncode']))
			xmloutput     = xmlhost.newChild(None, 'output', encode(check['output'], encoding))
			xmloutput.setProp('encoding', encoding)
			if check.has_key('timestamp'):
				xmltimestamp  = xmlhost.newChild(None, 'timestamp', str(check['timestamp']))
		else:
			# Service check result
			xmlservice    = xmlhost.newChild(None, 'service', None)
			xmlname       = xmlservice.newChild(None, 'description', encode(check['service_description'], encoding))
			xmlname.setProp('encoding', encoding)
			xmlreturncode = xmlservice.newChild(None, 'returncode', str(check['returncode']))
			xmloutput     = xmlservice.newChild(None, 'output', encode(check['output'], encoding))
			xmloutput.setProp('encoding', encoding)
			if check.has_key('timestamp'):
				xmltimestamp  = xmlservice.newChild(None, 'timestamp', str(check['timestamp']))

	return xmldoc


def xml_merge(xmldocs):
	checks = []
	for xmldoc in xmldocs:
		checks.extend(xml_to_dict(xmldoc))
	newxmldoc = xml_from_dict(checks)
	return newxmldoc


def check_mark_outdated(check, now, maxtimediff, markold):
	timedelta = now - check['timestamp']
	if timedelta > maxtimediff:
		check['output'] = 'Nag(ix)SC: Check result is %s(>%s) seconds old - %s' % (timedelta, maxtimediff, check['output'])
		if markold:
			check['returncode'] = 3
	return check


def reset_future_timestamp(timestamp, now):
	if timestamp <= now:
		return timestamp
	else:
		return now

##############################################################################

def encode_multipart(xmldoc, httpuser, httppasswd):
	BOUNDARY = mimetools.choose_boundary()
	CRLF = '\r\n'
	L = []
	L.append('--' + BOUNDARY)
	L.append('Content-Disposition: form-data; name="xmlfile"; filename="xmlfile"')
	L.append('Content-Type: application/xml')
	L.append('')
	L.append(xmldoc.serialize())
	L.append('--' + BOUNDARY + '--')
	L.append('')
	body = CRLF.join(L)
	content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
	headers = {'Content-Type': content_type, 'Content-Length': str(len(body))}

	if httpuser and httppasswd:
		headers['Authorization'] = 'Basic %s' % base64.b64encode(':'.join([httpuser, httppasswd]))

	return (headers, body)

##############################################################################

def daemonize(pidfile=None, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
	# 1st fork
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0)
	except OSError, e:
		sys.stderr.write("1st fork failed: (%d) %s\n" % (e.errno, e.strerror))
		sys.exit(1)
	# Prepare 2nd fork
	os.chdir("/")
	os.umask(0)
	os.setsid( )
	# 2nd fork
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0)
	except OSError, e:
		sys.stderr.write("2nd fork failed: (%d) %s\n" % (e.errno, e.strerror))
		sys.exit(1)

	# Try to write PID file
	if pidfile:
		pid = str(os.getpid())
		try:
			file(pidfile, 'w+').write('%s\n' % pid)
		except IOError:
			sys.stderr.write("Could not write PID file, exiting...\n")
			sys.exit(1)

	# Redirect stdin, stdout, stderr
	sys.stdout.flush()
	sys.stderr.flush()
	si = file(stdin, 'r')
	so = file(stdout, 'a+')
	se = file(stderr, 'a+', 0)
	os.dup2(si.fileno(), sys.stdin.fileno())
	os.dup2(so.fileno(), sys.stdout.fileno())
	os.dup2(se.fileno(), sys.stderr.fileno())

	return

##############################################################################

class MyHTTPServer(SocketServer.ForkingMixIn, BaseHTTPServer.HTTPServer):
	def __init__(self, server_address, HandlerClass, ssl=False, sslpemfile=None):
		if ssl:
			# FIXME: SSL is in Py2.6
			try:
				from OpenSSL import SSL
			except:
				print 'No Python OpenSSL wrapper/bindings found!'
				sys.exit(127)

			SocketServer.BaseServer.__init__(self, server_address, HandlerClass)
			context = SSL.Context(SSL.SSLv23_METHOD)
			context.use_privatekey_file (sslpemfile)
			context.use_certificate_file(sslpemfile)
			self.socket = SSL.Connection(context, socket.socket(self.address_family, self.socket_type))
		else:
			SocketServer.BaseServer.__init__(self, server_address, HandlerClass)
			self.socket = socket.socket(self.address_family, self.socket_type)

		self.server_bind()
		self.server_activate()


class MyHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def setup(self):
		self.connection = self.request
		self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
		self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

##############################################################################

def prepare_socket(socket_path):
	try:
		if socket_path.startswith('/'):
			s_family=socket.AF_UNIX
			s_sockaddr = socket_path
		elif socket_path.startswith('unix:'):
			s_family=socket.AF_UNIX
			s_sockaddr = socket_path[5:]
		elif socket_path.find(':') >= 0:
			s_port = socket_path.split(':')[-1]
			s_host = ':'.join(socket_path.split(':')[:-1])
			if s_host.startswith('[') and s_host.endswith(']'):
				s_host = s_host[1:-1]
			(s_family, s_socktype, s_proto, s_canonname, s_sockaddr) = socket.getaddrinfo(s_host, s_port, 0, socket.SOCK_STREAM)[0]
		else:
			return None
	except:
		return None

	return (s_family, s_sockaddr)


def read_socket(s_opts, commands):
	# print '%20s => %s %s' % (sock, s_family, s_sockaddr)

	s = socket.socket(s_opts[0], socket.SOCK_STREAM)
	s.connect(s_opts[1])
	for line in commands:
		if not line.endswith('\n'):
			line += '\n'
		s.send(line)
	s.shutdown(socket.SHUT_WR)

	answer = ''
	try:
		while True:
			s.settimeout(10)
			data = s.recv(32768)
			if data:
				answer += data
			else:
				break
	except socket.timeout:
		return ''

	return answer


def livestatus2dict(s_opts, host=None, service=None):
	checks = []

	# Get host information only if NO service specified
	if not service:
		commands = []
		commands.append('GET hosts\n')
		commands.append('Columns: name state plugin_output long_plugin_output last_check\n')
		if host:
			commands.append('Filter: name = %s' % host)
		answer = read_socket(s_opts, commands)

		for line in answer.split('\n')[:-1]:
			line = line.split(';')
			checks.append({'host_name':line[0], 'service_description':None, 'returncode':line[1], 'output':'\n'.join([line[2], line[3]]).rstrip(), 'timestamp':str(line[4])})

	# Get service information(s)
	commands = []
	commands.append('GET services\n')
	commands.append('Columns: host_name description state plugin_output long_plugin_output last_check\n')
	if host:
		commands.append('Filter: host_name = %s' % host)
	if service:
		commands.append('Filter: description = %s' % service)

	answer = read_socket(s_opts, commands)

	for line in answer.split('\n')[:-1]:
		line = line.split(';')
		checks.append({'host_name':line[0], 'service_description':line[1], 'returncode':line[2], 'output':'\n'.join([line[3], line[4]]).rstrip(), 'timestamp':str(line[5])})
				

	return checks
##############################################################################

