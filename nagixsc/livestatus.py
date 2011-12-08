# Nag(ix)SC -- nagixsc/livestatus.py
#
# Copyright (C) 2011 Sven Velt <sv@teamix.net>
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

import socket


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
		commands.append('Columns: name state plugin_output long_plugin_output perf_data last_check\n')
		commands.append('OutputFormat: python\n')
		if host:
			commands.append('Filter: name = %s' % host)
		answer = read_socket(s_opts, commands)
		try:
			answer = eval(answer)
		except:
			return (False, 'Bad output from livestatus for host check(s)!')

		for line in answer:
			output = '\n'.join([line[2], line[3]]).rstrip()
			if line[4]:
				output += '|' + line[4]
			checks.append({'host_name':line[0], 'service_description':None, 'returncode':line[1], 'output':output, 'timestamp':str(line[5])})

	# Get service information(s)
	commands = []
	commands.append('GET services\n')
	commands.append('Columns: host_name description state plugin_output long_plugin_output perf_data last_check\n')
	commands.append('OutputFormat: python\n')
	if host:
		commands.append('Filter: host_name = %s' % host)
	if service:
		commands.append('Filter: description = %s' % service)

	answer = read_socket(s_opts, commands)
	try:
		answer = eval(answer)
	except:
		return (False, 'Bad output from livestatus for service check(s)!')

	for line in answer:
		output = '\n'.join([line[3], line[4]]).rstrip()
		if line[5]:
			output += '|' + line[5]
		checks.append({'host_name':line[0], 'service_description':line[1], 'returncode':line[2], 'output':output, 'timestamp':str(line[6])})

	return (True, checks)
