#!/usr/bin/python
# Copyright 2009 Google Inc. All Rights Reserved.
"""Unit tests for requester.py."""

import time
import unittest

import realtime_bidding_pb2

import log
import requester


class MockGenerator(object):
  """A mock bid request generator that just returns a string."""

  def __init__(self, request_to_return=None):
    """Initializes a mock generator.

    Args:
      request_to_return: The request to return on each invocation, or None to
          use the default.
    """
    self.request = request_to_return
    if not self.request:
      self.request = realtime_bidding_pb2.BidRequest()
      self.request.id = '1234'

  def GenerateBidRequest(self):
    """Generates a string instead of a real bid request."""
    return self.request

  def GeneratePingRequest(self):
    """Generates a string instead of a ping request."""
    return self.request


class MockMethod(object):
  """A callable class to mock out methods in Requester."""

  def __init__(self, name, arg_values, return_values):
    """Initializes the mock method.

    Args:
      name: The name of the method this is replacing, for error messages.
      arg_values: A list of expected argument values.
      return_values: A list of values to return.

    Raises:
      ValueError: If the lengths of arg_values and return_values are not equal.
    """
    if len(arg_values) != len(return_values):
      raise ValueError('arg_values and return_values should be equal length.')
    self._name = name
    self._arg_values = arg_values
    self._return_values = return_values
    self._call_count = 0
    self._expected_call_count = len(self._return_values)

  def __call__(self, *args):
    """Make MockMethod instances callable."""
    self._call_count += 1
    # Index into arg_values and return_values.
    call_instance = self._call_count - 1
    if self._call_count > self._expected_call_count:
      raise ValueError('%s called too many times: %d' %
                       (self._name, self._call_count))
    if len(args) != len(self._arg_values[call_instance]):
      raise ValueError(
          '%s got an invalid number of arguments: %d, expected: %d' %
          (self._name, len(args), len(self._arg_values[call_instance])))
    for i in range(len(args)):
      if args[i] != self._arg_values[call_instance][i]:
        raise ValueError(
            '%s got an invalid argument at position %d: %s, expected: %s' %
            (self._name, i, args[i], self._arg_values[call_instance][i]))
    return self._return_values[call_instance]


def NoOp(*_):
  """A no-op function for mocking out methods.

  Args:
    _: Any args that the original method takes.
  """
  pass


class TestRequester(unittest.TestCase):
  """Tests the Requester class."""

  def setUp(self):
    self.logger = log.Logger()

  def testInitWithSeconds(self):
    """Tests that sepcifying seconds sets the correct fields."""
    self.requester = requester.Requester(None, None, None, 0.1, seconds=2)
    self.assertEqual(self.requester._time_between_requests, 0.1)
    self.assertEqual(self.requester._last_request_start_time, 0.0)
    self.assertEqual(self.requester._timedelta, 2)
    self.assertFalse(self.requester._use_requests_as_stop_signal)

  def testInitWithRequests(self):
    """Tests that specifying requests sets the correct fields."""
    self.requester = requester.Requester(None, None, None, 0.1, requests=2)
    self.assertEqual(self.requester._time_between_requests, 0.1)
    self.assertEqual(self.requester._last_request_start_time, 0.0)
    self.assertEqual(self.requester._max_requests, 2)
    self.assertTrue(self.requester._use_requests_as_stop_signal)

  def testInitWithSecondsAndRequests(self):
    """Tests initializing a Requester with both requests and seconds."""
    self.assertRaises(ValueError, requester.Requester, None, None, None, 0.1,
                      requests=1, seconds=1)

  def testGenerateRequest(self):
    generator = MockGenerator()
    self.requester = requester.Requester(generator, None, None, 0.1,
                                         requests=2)
    self.assertEqual(0, self.requester._generated_requests)
    request = self.requester._GenerateRequest()
    self.assertEqual(1, self.requester._generated_requests)
    self.assertEqual(generator.request, request)

  def testShouldSendMoreRequestsStopsOnMaxRequests(self):
    """Tests that ShouldSendMoreRequests stops at the maximum request count."""
    generator = MockGenerator()
    self.requester = requester.Requester(generator, None, None, 0.1,
                                         requests=2)
    # 0 requests sent.
    self.assertTrue(self.requester._ShouldSendMoreRequests())
    self.requester._GenerateRequest()
    # 1 requests sent.
    self.assertTrue(self.requester._ShouldSendMoreRequests())
    self.requester._GenerateRequest()
    # 2 requests sent, we ignore the lock since no multi-threading is going on.
    self.assertFalse(self.requester._ShouldSendMoreRequests())

  def testShouldSendMoreRequestsStopsAfterTimeout(self):
    """Tests that ShouldSendMoreRequests stops after the given timeout value."""
    self.requester = requester.Requester(MockGenerator(), None, None, 0.1,
                                         seconds=10)
    # Mock out _ShouldSendMoreRequests so that we can invoke Start to set the
    # start and stop time, while otherwise being a no-op.
    should_send_more_requests = self.requester._ShouldSendMoreRequests
    self.requester._ShouldSendMoreRequests = MockMethod(
        '_ShouldSendMoreRequests',
        [()],
        [False])
    current_time = time.time()
    # _GetCurrentTime will get invoked once in Start to set the start time, then
    # on each invocation of _ShouldSendMoreRequests.
    self.requester._GetCurrentTime = MockMethod(
        '_GetCurrentTime',
        [(), (), (), ()],
        [current_time,
         current_time + 1,
         current_time + 9,
         current_time + 10])
    # Sets _start_time and _stop_time.
    self.requester.Start()
    # Check that start and stop times are as expected.
    self.assertEqual(self.requester._start_time, current_time)
    self.assertEqual(self.requester._stop_time,
                     current_time + 10)

    # Restore _ShouldSendMoreRequests so we can test it.
    self.requester._ShouldSendMoreRequests = should_send_more_requests
    # 1 second has passed.
    self.assertTrue(self.requester._ShouldSendMoreRequests())
    # 9 seconds has passed.
    self.assertTrue(self.requester._ShouldSendMoreRequests())
    # 10 seconds has passed.
    self.assertFalse(self.requester._ShouldSendMoreRequests())

  def testWaitsBetweenRequestInvocations(self):
    """Tests that Requester waits between requests."""
    generator = MockGenerator()
    logger = log.Logger()
    self.requester = requester.Requester(generator, logger, None, 0.1,
                                         seconds=10)
    # Send two requests.
    self.requester._ShouldSendMoreRequests = MockMethod(
        '_ShouldSendMoreRequests', [(), (), ()], [True, True, False])
    # Wait should get called twice.
    self.requester._Wait = MockMethod('_Wait', [(), ()], [None, None])
    request_payload = generator.request.SerializeToString()
    self.requester._sender = MockMethod(
        '_sender',
        [(request_payload,), (request_payload,)],
        [(1, 'return value'), (1, 'return value')])

    self.requester.Start()
    self.assertEqual(2, self.requester._Wait._call_count)

  def testWait(self):
    """Tests that _Wait sleeps for the correct amount of time."""
    time_to_wait = 0.1
    self.requester = requester.Requester(None, None, None, time_to_wait,
                                         seconds=10)

    # current time = 1.0, last_request_start_time = 0.0 (i.e. first request),
    # time_to_wait = 0.1.
    # Wait shouldn't call _GetCurrentTime because this is the first request.
    # Wait should call sleep with time 0.1.
    time.sleep = MockMethod('sleep', [(0.1,)], [None])
    self.requester._GetCurrentTime = MockMethod('_GetCurrentTime', [], [])
    self.requester._Wait()
    self.assertEqual(1, time.sleep._call_count)

    # current time = 1.04, last_request_start_time = 1.01, time_to_wait = 0.1.
    # Wait should call _GetCurrentTime once to calculate time to wait.
    # Wait should call sleep with time of 0.1 - (1.04 - 1.01) = 0.07.
    last_request_time = 1.01
    self.requester._last_request_start_time = last_request_time
    current_time = 1.04
    self.requester._GetCurrentTime = MockMethod('_GetCurrentTime',
                                                [()],
                                                [current_time])
    time.sleep = MockMethod(
        'sleep',
        [(time_to_wait - (current_time - last_request_time),)],
        [None])
    self.requester._Wait()
    self.assertEqual(1, time.sleep._call_count)
    self.assertEqual(1, self.requester._GetCurrentTime._call_count)

    # Current time = 1.12, last_request_time = 1.01, time_to_wait = 0.1.
    # Wait should call _GetCurrentTime once to calculate time to wait.
    # Wait should not call sleep since too much time has elapsed.
    current_time = 1.12
    self.requester._GetCurrentTime = MockMethod('_GetCurrentTime',
                                                [()],
                                                [current_time])
    time.sleep = MockMethod('sleep', [], [])
    self.requester._Wait()
    self.assertEqual(0, time.sleep._call_count)
    self.assertEqual(1, self.requester._GetCurrentTime._call_count)


if __name__ == '__main__':
  unittest.main()
