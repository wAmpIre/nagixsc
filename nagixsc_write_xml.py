#!/usr/bin/python
#
# Nag(ix)SC -- nagixsc_write_xml.py
#
# Copyright (C) 2009-2010 Sven Velt <sv@teamix.net>
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

import optparse
import time

##############################################################################

import nagixsc

##############################################################################

checkresults = nagixsc.Checkresults()

parser = optparse.OptionParser()

parser.add_option('-o', '', dest='outfile', help='Output file name, "-" for STDOUT or HTTP POST URL')
parser.add_option('-l', '', dest='httpuser', help='HTTP user name, if outfile is HTTP(S) URL')
parser.add_option('-a', '', dest='httppasswd', help='HTTP password, if outfile is HTTP(S) URL')
parser.add_option('-e', '', dest='encoding', help='Encoding ("%s")' % '", "'.join(checkresults.available_encodings) )
parser.add_option('-q', '', action='store_true', dest='quiet', help='Be quiet')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(outfile='-')
parser.set_defaults(encoding='base64')
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

##############################################################################

# Put necessary options to checkresults
checkresults.options['outfile'] = options.outfile
checkresults.options['httpuser'] = options.httpuser
checkresults.options['httppasswd'] = options.httppasswd
checkresults.options['encoding'] = options.encoding

timestamp = long(time.time())

checkresults.checks = [
	{
		'host_name': 'host1',
		'service_description': 'Disk_Home',
		'output': 'DISK CRITICAL - free space: /home 775 MB (1% inode=91%);| /home=67584MB;61523;64941;0;68359',
		'returncode': '2',
		'timestamp': timestamp
	},
	{
		'host_name': 'host1',
		'output': 'OK - load average: 0.00, 0.00, 0.00|load1=0.000;5.000;10.000;0; load5=0.000;5.000;10.000;0; load15=0.000;5.000;10.000;0;',
		'returncode': '0',
		'service_description': 'Load',
		'timestamp': timestamp
	},
	{
		'host_name': 'host2',
		'output': 'PROCS OK: 163 processes',
		'returncode': '0',
		'service_description': 'Procs_Total',
		'timestamp': timestamp
	},
	{
		'host_name': 'host2',
		'output': 'SWAP OK - 79% free (1492 MB out of 1906 MB) |swap=1492MB;953;476;0;1906',
		'returncode': '0',
		'service_description': 'Swap', 
	},
	{
		'host_name': 'host1',
		'output': 'DISK OK - free space: / 2167 MB (22% inode=97%);| /=7353MB;8568;9044;0;9520',
		'returncode': '0',
		'service_description': 'Disk_Root',
		'timestamp': timestamp
	},
	{
		'host_name': 'host2',
		'output': 'USERS WARNING - 11 users currently logged in |users=11;10;15;0\n3 root sessions\n8 non-root sessions',
		'returncode': '1',
		'service_description': 'Users',
		'timestamp': timestamp
	},
]

# Output
(status, response) = checkresults.write_xml()

# Print error message or status message if we should not be quiet
if status == False:
	print response

