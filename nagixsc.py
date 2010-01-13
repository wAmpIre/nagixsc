import base64
import datetime
import libxml2
import shlex
import subprocess
import sys

def debug(level, verb, string):
	if level <= verb:
		print "%s: %s" % (level, string)


##############################################################################

def available_encodings():
	return ['base64', 'plain',]


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

def exec_check(host_name, service_descr, cmdline):
	try:
		cmd     = subprocess.Popen(shlex.split(cmdline), stdout=subprocess.PIPE)
		output  = cmd.communicate()[0].rstrip()
		retcode = cmd.returncode
	except OSError:
		output  = 'Could not execute "%s"' % cmdline
		retcode = 127

	return {'host_name':host_name, 'service_description':service_descr, 'returncode':retcode, 'output':output, 'timestamp':datetime.datetime.now().strftime('%s')}


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

		if retcode and output:
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

