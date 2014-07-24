#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_httpd.py
#
# Copyright (C) 2009-2011 Sven Velt <sv@teamix.net>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import ConfigParser
import cStringIO
import optparse
import os
import sys

##############################################################################

import nagixsc

##############################################################################

defaults4cfgfile = cStringIO.StringIO('''
[server]
ip: 0.0.0.0
port: 15651
ssl: false
sslcert:
pidfile: /var/run/nagixsc_httpd.pid
enable_executor: false
enable_acceptor: false
[executor]
conf_dir:
remote_administration: false
livestatus_socket:
[executor/users]
[executor/admins]
[acceptor]
mode:
checkresult_dir:
commandfile_path:
acl: false
[acceptor/users]
[acceptor/admins]
[acceptor/acl_allowed_hosts_list]
[acceptor/acl_allowed_hosts_re]
''')

##############################################################################

##############################################################################

def main():
	# New HTTP Server
	server = nagixsc.http.NagixSC_HTTPServer(defaults=defaults4cfgfile)

	# Command line options
	parser = optparse.OptionParser()

	parser.add_option('-c', '', dest='cfgfile', help='Config file')
	parser.add_option('-d', '--daemon', action='store_true', dest='daemon', help='Daemonize, go to background')
	parser.add_option('', '--nossl', action='store_true', dest='nossl', help='Disable SSL (overwrites config file)')

	parser.set_defaults(cfgfile='/etc/nagixsc/httpd.cfg')

	(server.options, server.args) = parser.parse_args()

	server.read_config_file()

	if server.options.daemon:
		nagixsc.daemon.daemonize(pidfile=server.config_server['pidfile'])

	server.socket_init()
	try:
		server.serve_forever()
	except:
		server.socket.close()



if __name__ == '__main__':
	main()

