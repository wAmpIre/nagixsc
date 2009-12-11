#!/usr/bin/python

import cherrypy
import os
import re
import subprocess

config = {	'server.socket_host':		'0.0.0.0',
			'server.socket_port':		15667,
			'log.screen':				False,
			'log.access_file':			None,
			'log.error_file':			None,
		}

users = {	'nagixsc':		'019b0966d98fb71d1a4bc4ca0c81d5cc',		# PW: nagixsc
		}

XMLFILESIZE=102400
X2N='./nagixsc_xml2nagios.py -O passive -vvv -f -'

class CGI2Nagios:
	def default(*args, **kwargs):
		cmdline = X2N

		if len(args) >= 3:
			print 'Ignoring arguments: ', args[2:]

		if len(args) >= 2:
			c_configfile = args[1]
		else:
			c_configfile = ''

		cherrypy.lib.auth.basic_auth('Nag(ix)SC HTTP', users)

		print kwargs
		if kwargs.has_key('xmlfile'):
			if type(kwargs['xmlfile']) == str:
				xmltext = kwargs['xmlfile']
			else:
				xmltext = kwargs['xmlfile'].file.read(XMLFILESIZE+1)

			if len(xmltext) > 0:
				try:
					cmd     = subprocess.Popen(cmdline.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
					output  = cmd.communicate(xmltext)[0].rstrip()
					cherrypy.response.headers['Content-Type'] = 'text/plain'
					return output
				except OSError:
					return 'Nag(IX)SC - Could not execute "%s"' % cmdline

				return 'Nag(IX)SC - OK'
			else:
				return 'Nag(IX)SC - No data received'
		else:
			return """
			<html><body>
				<form action="." method="post" enctype="multipart/form-data">
				filename: <input type="file" name="xmlfile" /><br />
				<input type="submit" />
				</form>
			</body></html>
			"""

	default.exposed = True

print 'curl -v -u nagixsc:nagixsc -F \'xmlfile=@xml/nagixsc.xml\' http://127.0.0.1:15667/foo/\n\n\n\n'

cherrypy.config.update(config)
cherrypy.tree.mount(CGI2Nagios(), '')
cherrypy.quickstart(config=config)

