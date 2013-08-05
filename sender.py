#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.
"""A class that sends randomly generated bid requests to an HTTP server."""

import httplib
import urlparse

CONTENT_TYPE = "application/octet-stream"
CONTENT_TYPE_HEADER = "Content-type"


class HTTPSender(object):
  """Sends requests to the given url.

  You can send things by either invoking the Send() method implicitly or just
  calling an instance of the class, which invokes the Send method."""

  def __init__(self, url):
    parsed = urlparse.urlparse(url)
    # Set some defaults.
    self._port = '80'
    self._path = '/'

    if not parsed[0] and parsed[0] != 'http':
      raise ValueError("URL scheme must be HTTP.")
    if not parsed[1]:
      raise ValueError("URL must have a hostname.")

    netloc = parsed[1]
    self._host = netloc
    # Try to find a valid port, otherwise assume the netloc is just the
    # hostname.
    if netloc.find(":") != -1:
      components = netloc.rsplit(":", 1)
      if len(components) == 2:
        host_str = components[0]
        port_str = components[1]
        int(port_str)
        # Valid numerical port, set host and port accordingly
        self._port = port_str
        self._host = host_str

    if (parsed[2] or parsed[3] or parsed[4] or parsed[5]):
      self._path = urlparse.urlunparse(('', '', parsed[2], parsed[3],
                                        parsed[4], parsed[5]))
    self._connection = None

  def __call__(self, *args):
    """Makes instances of HTTPSender callable.

    Args:
      args: Any arguments that should be passed to Send.

    Returns:
      The return value of Send."""
    return self.Send(*args)

  def Send(self, payload):
    """Sends the given payload to the pre-configured URL.

    Args:
      payload: Data to send.

    Returns:
      A tuple of the form (<http response code>, <http response payload>).
    """
    if not self._connection:
      self._connection = httplib.HTTPConnection(self._host, self._port)
    self._connection.request('POST', self._path, payload,
                             {CONTENT_TYPE_HEADER: CONTENT_TYPE})
    response = self._connection.getresponse()
    status = response.status
    data = response.read()
    return (status, data)
