#!/usr/bin/python

import cherrypy
import os
import re
import subprocess

config = {	'server.socket_host':		'0.0.0.0',
			'server.socket_port':		15666,
			'log.screen':				False,
			'log.access_file':			None,
			'log.error_file':			None,
		}

users = {	'nagixsc':		'019b0966d98fb71d1a4bc4ca0c81d5cc',		# PW: nagixsc
		}

CONFDIR='./examples'
C2X='./nagixsc_conf2xml.py'
class Conf2CGI:
	def default(*args, **kwargs):
		cmdline = C2X

		if len(args) >= 5:
			print 'Ignoring arguments: ', args[4:]

		if len(args) >= 4:
			c_service = args[3]
		else:
			c_service = ''

		if len(args) >= 3:
			c_host = args[2]
		else:
			c_host = ''

		if len(args) >= 2:
			c_configfile = args[1]
		else:
			c_configfile = ''
			print 'No config file specified!'

		if c_configfile:
			cherrypy.lib.auth.basic_auth('Nag(ix)SC HTTP', users)

			if re.search('\.\.', c_configfile):
				return 'Found ".." in config file name'
			if not re.search('^[a-zA-Z0-9-_\.]+$', c_configfile):
				return 'Config file name contains invalid characters'
			cmdline += ' -c ' + os.path.join(CONFDIR, c_configfile)

			if c_host:
				cmdline += ' -H %s' % c_host
				if c_service:
					cmdline += ' -D %s' % c_service
			try:
				cmd     = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE)
				output  = cmd.communicate()[0].rstrip()
			except OSError:
				return 'Could not execute "%s"' % cmdline

			cherrypy.response.headers['Content-Type'] = 'text/xml'
			return output
		else:
			return '42'

	default.exposed = True

cherrypy.config.update(config)
cherrypy.tree.mount(Conf2CGI(), '')
cherrypy.quickstart(config=config)

