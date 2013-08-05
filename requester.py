#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.
"""A class that drives a request sender."""
import datetime
import optparse
import os
import random
import threading
import time

import generator
import log
import sender


GOOD_LOG_TEMPLATE = 'good-%s.log'
PROBLEMATIC_LOG_TEMPLATE = 'problematic-%s.log'
INVALID_LOG_TEMPLATE = 'invalid-%s.log'
ERROR_LOG_TEMPLATE = 'error-%s.log'
SNIPPET_LOG_TEMPLATE = 'snippets-%s.html'


def CreateRequesters(num_senders, max_qps, url, logger_obj, google_ids=None,
                     seconds=0, requests=0, interval=0,
                     instream_video_proportion=0.0, mobile_proportion=0.0,
                     adgroup_ids=None):
  """Creates num_senders threads, and a sender.HTTPSender object for each.

  Args:
    num_senders: The number of sender threads to create.
    max_qps: Max overall qps.
    url: The URL to which senders will send requests.
    logger_obj: A log.Logger object.
    google_ids: A list of Google user IDs or None to randomly generate user ids.
    seconds: The number of seconds to continue sending requests.
    requests: The number of requests to send.
    interval: The number of seconds to wait between thread creation.
    instream_video_proportion: Proportion of requests to genereate that are for
        instream video slots.
    mobile_proportion: Proportion of mobile requests to be generated.
    adgroup_ids: A list of AdGroup IDs or None to randomly generate
        pretargeted AdGroup IDs.

  Returns:
    A list of Requester objects.
  """
  seconds = seconds or 0
  requests = requests or 0
  # Create at most max_qps/10 threads, giving each thread at least 10 QPS.
  num_senders = min(num_senders, max_qps / 10)
  num_senders = max(num_senders, 1)  # Avoid setting num_senders to 0.
  send_rate_per_sender = num_senders / float(max_qps)
  requests_per_sender = requests / num_senders
  requesters = []
  for i in xrange(num_senders):
    generator_obj = generator.RandomBidGeneratorWrapper(
        google_ids, instream_video_proportion, mobile_proportion, adgroup_ids)
    sender_obj = sender.HTTPSender(url)
    requester = Requester(generator_obj, logger_obj, sender_obj,
                          send_rate_per_sender, seconds, requests_per_sender)
    requester.name = 'requester-thread-%d' % i
    requesters.append(requester)
    if interval:
      time.sleep(interval)
  return requesters


class Requester(threading.Thread):
  """A thread which generates and sends bid requests.

  A Requester can generate either a specific number of requests, or generate
  requests for a specific number of seconds. In either case requests are sent at
  a specific interval configured through the time_between_requests parameter to
  the constructor.
  """

  def __init__(self, generator_obj, logger_obj, sender_obj,
               time_between_requests, seconds=None, requests=None):
    """Initializes a Requester object.

    Args:
      generator_obj: An RandomBidGenerator object.
      logger_obj: A logging.Logger object.
      sender_obj: A sender.HTTPSender object.
      time_between_requests: The time in (fractional) seconds to wait between
          requests.
      seconds: Number of seconds to run test. Specify only one of seconds or
          requests.
      requests: Number of requests to generate. Specify only one of seconds or
          requests.

    Raises:
      ValueError: If none or both of seconds and requests are specified.
    """
    super(Requester, self).__init__()
    self._generator = generator_obj
    self._logger = logger_obj
    self._sender = sender_obj
    self._time_between_requests = float(time_between_requests)
    self._generated_requests = 0
    self._last_request_start_time = 0.0
    if ((seconds and requests) or
        (not seconds and not requests)):
      raise ValueError('Exactly one of seconds and requests must be'
                       ' specified')
    if seconds:
      self._timedelta = float(seconds)
      self._use_requests_as_stop_signal = False
    else:
      self._max_requests = requests
      self._use_requests_as_stop_signal = True

  def run(self):
    """Thread's run method, simply calls Start().

    This is separate from Start so that unit-tests can invoke start without
    starting a new thread.
    """
    self.Start()

  def Start(self):
    """Starts sending requests."""
    if not self._use_requests_as_stop_signal:
      self._start_time = self._GetCurrentTime()
      self._stop_time = self._start_time + self._timedelta

    while self._ShouldSendMoreRequests():
      request = self._GenerateRequest()
      payload = request.SerializeToString()
      request_start_time = self._GetCurrentTime()
      status, data = self._sender(payload)
      self._logger.LogSynchronousRequest(request, status, data)
      self._Wait()
      self._last_request_start_time = request_start_time

  def _Wait(self):
    """Waits some time to throttle request rate.

    It's convenient to have this as a separate method for mocking.
    """
    time_to_wait = self._time_between_requests

    # Subtract time since the start of the last request.
    if self._last_request_start_time:
      time_since_last_request = (self._GetCurrentTime() -
                                 self._last_request_start_time)
      time_to_wait = max(0, time_to_wait - time_since_last_request)

    # Don't sleep if too much time has passed since the last request.
    if time_to_wait:
      time.sleep(time_to_wait)

  def _ShouldSendMoreRequests(self):
    """Returns True if more requests should be sent.

    Returns:
      True if more requests should be sent, False otherwise.
    """
    if self._use_requests_as_stop_signal:
      return self._generated_requests < self._max_requests
    else:
      return self._GetCurrentTime() < self._stop_time

  def _GenerateRequest(self):
    """Generates and returns a request.

    Returns:
      A randomly generated BidRequest.
    """
    # Generate ping requests 1% of the time.
    if random.random() < 0.01:
      bid_request = self._generator.GeneratePingRequest()
    else:
      bid_request = self._generator.GenerateBidRequest()
    self._generated_requests += 1
    return bid_request

  def _GetCurrentTime(self):
    """Returns the current time as a POSIX timestamp (seconds since epoch).

    It's convenient to have this as a separate method for mocking.

    Returns:
      The current time as a POSIX timestamp (floating point seconds since the
      epoch).
    """
    return time.time()


def PrintSummary(logger, encrypted_price):
  """Prints a summary of results optionally substituting an encrypted price.

  Args:
    logger: A log.Logger object.
    encrypted_price: A string representing an encrypted price to substitue for
      the WINNING_PRICE macro, or None to substitute a non-encrypted number.
  """
  logger.Done()
  summarizer = log.LogSummarizer(logger)
  if encrypted_price:
    summarizer.SetSampleEncryptedPrice(encrypted_price)
  summarizer.Summarize()
  timestamp = str(datetime.datetime.now())
  timestamp = timestamp.replace(' ', '-', timestamp.count(' '))
  timestamp = timestamp.replace(':', '', timestamp.count(':'))
  good_log_filename = GOOD_LOG_TEMPLATE % timestamp
  good_log = open(good_log_filename, 'w')
  problematic_log_filename = PROBLEMATIC_LOG_TEMPLATE % timestamp
  problematic_log = open(problematic_log_filename, 'w')
  invalid_log_filename = INVALID_LOG_TEMPLATE % timestamp
  invalid_log = open(invalid_log_filename, 'w')
  error_log_filename = ERROR_LOG_TEMPLATE % (timestamp)
  error_log = open(error_log_filename, 'w')
  snippet_log_filename = SNIPPET_LOG_TEMPLATE % (timestamp)
  snippet_log = open(snippet_log_filename, 'w')
  summarizer.WriteLogFiles(good_log, problematic_log, invalid_log, error_log,
                           snippet_log)
  good_log.close()
  problematic_log.close()
  invalid_log.close()
  error_log.close()
  snippet_log.close()
  summarizer.PrintReport()

  # Cleanup by deleting empty files.
  for file_name in [good_log_filename, problematic_log_filename,
                    invalid_log_filename, error_log_filename,
                    snippet_log_filename]:
    if not os.path.getsize(file_name):
      os.remove(file_name)


def SetupCommandLineOptions():
  """Sets up command line option parsing.

  Returns:
    An optparse.OptionParser object.
  """
  parser = optparse.OptionParser()
  parser.add_option('--url', help='URL of the bidder.')
  parser.add_option('--max_qps', type='int',
                    help='Maximum queries per second to send to the bidder.')
  parser.add_option('--seconds', type='int',
                    help='Total duration in seconds. Specify exactly one of '
                    '--seconds or --requests.')
  parser.add_option('--requests', type='int',
                    help='Total number of requests to send. Specify exactly '
                    'one of --seconds or --requests.')
  parser.add_option('--num_threads', type='int',
                    default=20, help='Maximum number of threads to use. The '
                    'actual number of threads may be lower.')
  parser.add_option('--thread_interval', type='int',
                    default=0.2, help='Interval between thread creation, allows'
                    ' for a gradual rampup')
  parser.add_option('--sample_encrypted_price', type='string',
                    help='Use the given string as the encrypted price when'
                    'rendering snippets. Pass one of the sample encrypted'
                    'prices provided by Google.')
  parser.add_option('--google_user_ids_file', type='string',
                    help='Path to a file containing a list of Google IDs one '
                    'per line. These will be used instead of randomly '
                    ' generated ID if specified.')
  parser.add_option('--instream_video_proportion', type='float',
                    default=0.1,
                    help='Proportion of requests that are for in-stream video'
                    ' slots (0.1 by default).')
  parser.add_option('--mobile_proportion', type='float',
                    default=0.2,
                    help='Proportion of requests that are for mobile slots '
                    '(0.2 by default).')
  parser.add_option('--adgroup_ids_file', type='string',
                    help='Path to a file containing a list of AdGroup IDs '
                    'one per line. These will be used in the matching ad data '
                    'instead of randomly generated IDs.')
  return parser


def ParseCommandLineArguments(parser):
  """Parses command line arguments and handles error checking.

  Args:
    parser: An optparse.OptionParser object initialized with options.

  Returns:
    The result of OptionParser.parse after it has been checked for errors.
  """
  opts, args = parser.parse_args()
  if args:
    parser.error('unexpected positional arguments "%s".' % ' '.join(args))
  if ((opts.requests and opts.seconds) or
      (not opts.requests and not opts.seconds)):
    parser.error('exactly one of --requests and --seconds requires a value.')
  if not opts.url:
    parser.error('--url requires a value.')
  if not opts.max_qps:
    parser.error('--max_qps requires a value.')
  return opts


def GetIdsFromFile(filename):
  """Reads IDs, one per line, from the given file and returns them in a list.

  Args:
    filename: A filename, the file should contain one ID per line.

  Returns:
    A list of IDs read from the file or None if there were problems
    reading the file.
  """
  if not os.path.exists(filename):
    print 'Invalid file: %s' % filename
    return None

  try:
    ids = None
    with open(filename, 'r') as ids_file:
      ids = [l.strip() for l in ids_file if l.strip()]
    return ids
  except IOError:
    print 'Could not open file for reading: %s' % filename
    return None


def main():
  parser = SetupCommandLineOptions()
  opts = ParseCommandLineArguments(parser)
  logger_obj = log.Logger()

  google_user_ids = None
  if opts.google_user_ids_file:
    google_user_ids = GetIdsFromFile(opts.google_user_ids_file)

  adgroup_ids = None
  if opts.adgroup_ids_file:
    adgroup_ids = [int(i) for i in GetIdsFromFile(opts.adgroup_ids_file)]

  if (opts.instream_video_proportion + opts.mobile_proportion) > 1:
    raise Exception('Video and mobile proportions exceed 1')

  requesters = CreateRequesters(opts.num_threads, opts.max_qps, opts.url,
                                logger_obj, google_user_ids, opts.seconds,
                                opts.requests, opts.thread_interval,
                                opts.instream_video_proportion,
                                opts.mobile_proportion, adgroup_ids)
  for requester in requesters:
    requester.start()

  for requester in requesters:
    requester.join()

  PrintSummary(logger_obj, opts.sample_encrypted_price)


if __name__ == '__main__':
  main()
