# Nag(ix)SC -- nagixsc/daemon.py
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

import os
import sys


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

