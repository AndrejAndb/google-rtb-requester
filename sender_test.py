#!/usr/bin/python
# Copyright 2009 Google Inc. All Rights Reserved.
"""Unit tests for requester.py."""

import unittest

import sender


class TestHTTPSender(unittest.TestCase):
  """Tests the HTTPSender class."""

  def testInitWithNoScheme(self):
    """Tests initializing with a URL with no scheme."""
    self.assertRaises(ValueError, sender.HTTPSender, 'noscheme.com')

  def testInitWithoutPortOrPath(self):
    """Tests initializing with a URL with no port or path."""
    self.sender = sender.HTTPSender('http://google.com')
    self.assertEqual('google.com', self.sender._host)
    self.assertEqual('/', self.sender._path)
    self.assertEqual('80', self.sender._port)

  def testInitWithoutPortOrPathWithPathDelimiter(self):
    """Tests with a URL with no port or path, but with a path delimiter."""
    self.sender = sender.HTTPSender('http://google.com/')
    self.assertEqual('google.com', self.sender._host)
    self.assertEqual('/', self.sender._path)
    self.assertEqual('80', self.sender._port)

  def testInitWithoutPortOrPathWithPortDelimiter(self):
    """Tests with a URL with no port or path, but with a port delimiter."""
    self.assertRaises(ValueError, sender.HTTPSender, 'http://google.com:')

  def testInitWithPortWithoutPath(self):
    """Tests with a URL with a port, and no path."""
    self.sender = sender.HTTPSender('http://google.com:8080')
    self.assertEqual('google.com', self.sender._host)
    self.assertEqual('/', self.sender._path)
    self.assertEqual('8080', self.sender._port)

  def testInitWithPathWithoutPort(self):
    """Tests with a URL with a path, and no port."""
    self.sender = sender.HTTPSender('http://google.com/mypath/hello')
    self.assertEqual('google.com', self.sender._host)
    self.assertEqual('/mypath/hello', self.sender._path)
    self.assertEqual('80', self.sender._port)

  def testInitWithPathAndPort(self):
    """Tests with a URL with a path and port."""
    self.sender = sender.HTTPSender('http://google.com:1234/mypath/hello')
    self.assertEqual('google.com', self.sender._host)
    self.assertEqual('/mypath/hello', self.sender._path)
    self.assertEqual('1234', self.sender._port)

if __name__ == '__main__':
  unittest.main()
