# Nag(ix)SC -- nagixsc/http.py
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

import BaseHTTPServer
import SocketServer
import mimetools



def encode_multipart(xmldoc, httpuser=None, httppasswd=None):
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

if 'ForkingMixIn' in SocketServer.__dict__:
	MixInClass = SocketServer.ForkingMixIn
else:
	MixInClass = SocketServer.ThreadingMixIn

class MyHTTPServer(MixInClass, BaseHTTPServer.HTTPServer):
	def __init__(self, server_address, HandlerClass, ssl=False, sslpemfile=None):
		SocketServer.BaseServer.__init__(self, server_address, HandlerClass)

		if ssl:
			try:
				import ssl
				self.socket = ssl.wrap_socket(socket.socket(self.address_family, self.socket_type), keyfile=sslpemfile, certfile=sslpemfile)

			except:

				try:
					from OpenSSL import SSL
				except:
					print 'No Python SSL or OpenSSL wrapper/bindings found!'
					sys.exit(127)

				context = SSL.Context(SSL.SSLv23_METHOD)
				context.use_privatekey_file (sslpemfile)
				context.use_certificate_file(sslpemfile)
				self.socket = SSL.Connection(context, socket.socket(self.address_family, self.socket_type))

		else:
			self.socket = socket.socket(self.address_family, self.socket_type)

		self.server_bind()
		self.server_activate()


class MyHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def setup(self):
		self.connection = self.request
		self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
		self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)
