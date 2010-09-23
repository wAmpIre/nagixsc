#!/usr/bin/python

import os
import re
import time

##############################################################################
from nagixsc import *
##############################################################################

def check_dir(dirpath):
	if not os.path.isdir(dirpath):
		# dirpath does not exist, try to create it
		try:
			os.path.os.mkdir(dirpath, 0777) # FIXME
		except OSError:
			print 'Could not create directory "%s"!' % dirpath
			sys.exit(1)

	if not os.access(dirpath,os.W_OK):
		# dirpath is not writeable
		print 'No write access to directory "%s"!' % dirpath
		sys.exit(1)

##############################################################################

spoolpath_base = '/tmp/nagixsc.spool'
spoolpath_new = os.path.join(spoolpath_base, 'new')
spoolpath_work = os.path.join(spoolpath_base, 'work')
spoolpath_done = os.path.join(spoolpath_base, 'done')

for d in [spoolpath_base, spoolpath_new, spoolpath_work, spoolpath_done]:
	check_dir(d)

# Output XML files to this directory
outdir = os.path.join(spoolpath_base, 'xmlout')
check_dir(outdir)

service_analyzer = re.compile("^LASTSERVICECHECK::'?(\d+)'?\s+HOSTNAME::'?([^']+)'?\s+SERVICEDESC::'?([^']+)'?\s+SERVICESTATEID::'?(\d+)'?\s+SERVICEOUTPUT::'?([^']*)'?\s+LONGSERVICEOUTPUT::'?([^']*)'?$")
host_analyzer = re.compile("LASTHOSTCHECK::'?(\d+)'?\s+HOSTNAME::'?([^']+)'?\s+HOSTSTATEID::'?(\d+)'?\s+HOSTOUTPUT::'?([^']*)'?\s+LONGHOSTOUTPUT::'?([^']*)'?$")


while True:
	if os.listdir(spoolpath_new):
		checks = []
		files_done = []
		for filename in os.listdir(spoolpath_new):
			spoolfile = os.path.join(spoolpath_work, filename)
			os.rename(os.path.join(spoolpath_new, filename), spoolfile)

			# Work with file
			f = open(spoolfile)

			print 'Read ' + spoolfile
			for line in f:
				if line.startswith('LASTSERVICECHECK'):
					m = service_analyzer.match(line)
					if m:
						checks.append({'host_name':m.group(2), 'service_description':m.group(3), 'returncode':m.group(4), 'output':'\n'.join(m.group(5,6)), 'timestamp':m.group(1)})

				elif line.startswith('LASTHOSTCHECK'):
					m = host_analyzer.match(line)
					if m:
						checks.append({'host_name':m.group(2), 'service_description':None, 'returncode':m.group(3), 'output':'\n'.join(m.group(4,5)), 'timestamp':m.group(1)})

			f.close()
			files_done.append(filename)

		outfilename = str(int(time.time())) + '.xml'
		xmldoc = xml_from_dict(checks)
		xmldoc.saveFile(os.path.join(outdir, outfilename)) # FIXME
		for filename in files_done:
			os.rename(os.path.join(spoolpath_work, filename), os.path.join(spoolpath_done, filename))
		print 'Written ' + outfilename

	time.sleep(5)

