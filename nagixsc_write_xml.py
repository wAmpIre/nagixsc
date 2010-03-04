#!/usr/bin/python

import nagixsc
import optparse

parser = optparse.OptionParser()

parser.add_option('-o', '', dest='outfile', help='(Path and) file name of status file, default STDOUT')
parser.add_option('-v', '', action='count', dest='verb', help='Verbose output')

parser.set_defaults(outfile='-')
parser.set_defaults(verb=0)

(options, args) = parser.parse_args()

checks = [{'host_name': 'host1',
  'output': 'Nag(ix)SC: Check result is 24535725(>14400) seconds old  - DISK CRITICAL - free space: /home 775 MB (1% inode=91%);| /home=67584MB;61523;64941;0;68359',
  'returncode': '2',
  'service_description': 'Disk_Home',
  'timestamp': 1234443420},
 {'host_name': 'host1',
  'output': 'Nag(ix)SC: Check result is 24535725(>14400) seconds old  - OK - load average: 0.00, 0.00, 0.00|load1=0.000;5.000;10.000;0; load5=0.000;5.000;10.000;0; load15=0.000;5.000;10.000;0;',
  'returncode': '0',
  'service_description': 'Load',
  'timestamp': 1234443420},
 {'host_name': 'host2',
  'output': 'Nag(ix)SC: Check result is 24535735(>14400) seconds old  - PROCS OK: 163 processes',
  'returncode': '0',
  'service_description': 'Procs_Total',
  'timestamp': 1234443410},
 {'host_name': 'host2',
  'output': 'Nag(ix)SC: Check result is 24535715(>14400) seconds old  - SWAP OK - 79% free (1492 MB out of 1906 MB) |swap=1492MB;953;476;0;1906',
  'returncode': '0',
  'service_description': 'Swap', },
 {'host_name': 'host1',
  'output': 'Nag(ix)SC: Check result is 24535725(>14400) seconds old  - DISK OK - free space: / 2167 MB (22% inode=97%);| /=7353MB;8568;9044;0;9520',
  'returncode': '0',
  'service_description': 'Disk_Root',
  'timestamp': 1234443420},
 {'host_name': 'host2',
  'output': 'Nag(ix)SC: Check result is 24535735(>14400) seconds old  - USERS WARNING - 11 users currently logged in |users=11;10;15;0\n3 root sessions\n8 non-root sessions',
  'returncode': '1',
  'service_description': 'Users',
  'timestamp': 1234443410}]

xmldoc = nagixsc.xml_from_dict(checks)
xmldoc.saveFile(options.outfile)

