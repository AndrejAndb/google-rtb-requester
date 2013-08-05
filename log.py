#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.
"""Contains classes for logging Real Time Bidder requests and responses."""

import base64
import cgi
import datetime
import httplib
import random
import re
import sys
import threading
import urllib
import urlparse

import google.protobuf.message
import realtime_bidding_pb2

TEMPLATE_PARAM_REGEX = re.compile('%%P(.)%%')


class Record(object):
  """A record of each request/response pair."""
  def __init__(self, bid_request, status_code, payload):
    self.bid_request = bid_request
    self.status = status_code
    self.payload = payload

    # The following fields get filled in by the LogSummarizer after the
    # response protocol buffer has been succesfully parsed.

    # A list of strings with problem descriptions.
    self.problems = []
    # A realtime_bidding_pb2.BidResponse instance.
    self.bid_response = None
    # A map of ad index -> validated HTML snippet (after macro substitutions).
    self.html_snippets = {}


class LoggerException(Exception):
  """An exception thrown for invalid uses of a Logger."""
  pass


class Logger(object):
  """A class that keeps a log of all requests and responses."""

  def __iter__(self):
    if not self._done:
      raise LoggerException('Only locked Loggers are iterable.')
    return self

  def __getitem__(self, item):
    if not self._done:
      raise LoggerException('Only locked Loggers are iterable.')
    return self._records[item]

  def next(self):
    if not self._done:
      raise LoggerException('Only locked Loggers can are iterable.')
    if self._current_iteration >= len(self._records):
      self._current_iteration = 0
      raise StopIteration

    c = self._current_iteration
    self._current_iteration += 1
    return self._records[c]

  def __init__(self):
    # Stores Record objects.
    self._records = []
    self._record_lock = threading.Lock()
    self._current_iteration = 0
    self._done = False

  def Done(self):
    """Signals that logging is done, locking this object to modifications."""
    self._record_lock.acquire()
    try:
      self._done = True
    finally:
      self._record_lock.release()

  def IsDone(self):
    """Returns True if this logger has been locked for updates."""
    self._record_lock.acquire()
    try:
      return self._done
    finally:
      self._record_lock.release()

  def LogSynchronousRequest(self, bid_request, status_code, payload):
    """Logs a synchronous request.

    Args:
      bid_request: A realtime_bidding_pb2.BidRequest object.
      status_code: The HTTP status code.
      payload: The HTTP response payload.

    Returns:
      True if the request was logged, False otherwise.
    """
    if self.IsDone():
      return False

    self._record_lock.acquire()
    try:

      record = Record(bid_request, status_code, payload)
      self._records.append(record)
    finally:
      self._record_lock.release()

    return True


def EscapeUrl(input_str):
  """Returned the URL-escaped version of input_str.

  The input is URL-escaped as documented at:
  https://sites.google.com/a/google.com/adx-rtb/technical-documentation/response

  Args:
    input_str: A string to URL-escape.

  Returns:
    The URL-escaped version of input_str.
  """
  return urllib.quote_plus(input_str, '!()*,-./:_~')


class LogSummarizer(object):
  """Summarizes information stored in a Logger and outputs a report."""

  REQUEST_ERROR_MESSAGES = {
      'not-ok': 'The HTTP response code was not 200/OK.',
  }

  RESPONSE_ERROR_MESSAGES = {
      'empty': 'Response is empty (0 bytes).',
      'parse-error': 'Response could not be parsed.',
      'uninitialized': 'Response did not contain all required fields.',
      'no-processing-time': 'Response contains no processing time information.',
      'ads-in-ping': 'Response for ping message contains ads.',
  }

  AD_ERROR_TEMPLATE = 'Ad %d: %s'
  AD_ERROR_MESSAGES = {
      'no-types': (
          'none of { video_url, html_snippet, snippet_template } '
          'are set, exactly one must be set.'),
      'mulitple-types': (
          'more than one of { video_url, html_snippet, snippet_template } '
          'are set, exactly one must be set.'),
      'invalid-video-url': 'invalid video_url: ',
      'no-video-in-request': (
          'returned video ad when the request did not contain a Video '
          'submessage'),
      'video-in-request': (
          'returned HTML ad when the request contained a Video submessage'),
      'empty-snippet': 'snippet is empty.',
      'no-adslots': 'ad does not target any adslots.',
      'no-click-through-urls': 'ad does not contain any click-through urls.',
      'invalid-url': 'invalid click-through URL: ',
      'template-and-parameters': (
          'template ads must declare both snippet_template and '
          'template_parameter fields.'),
      'non-int-params': (
          'Template parameters must be %%PN%% where N is an int, invalid '
          'parameters: '),
      'non-consecutive-params': (
          'Template parameters must be numbered 0..N-1, where N is the '
          'number of parameters.'),
      'param-mismatch': (
          'Number of parameters in template must match length of '
          'template_parameter field.'),
      'buyer-id-in-response':
          'Template ads must not declare buyer_creative_id in the BidResopnse.',
      'no-id-in-parameter': 'Template ads must declare buyer_creative_id.',
      'no-value-in-parameter': 'Template ads must declare parameter_value.',
      'url-in-response':
          'Template ads must not declare click_through_url in the BidResopnse.',
      'no-bounds':
          'Template ads must declare bounds (left, right, top, bottom).',
      'at-least-two-params':
          'Template ads must have at least 2 parameters, given: ',
      'at-most-four-params':
          'Template ads must have at most 4 parameters, given: ',
      'backup-not-at-end': 'Backup template parameters must be at the end.',
      'invalid-backup-reference':
          'Backup template parameters must reference a valid index, invalid: ',
      'one-dimension':
          'Template ads should stack either vertically or horizontally.',
      'invalid-template-dimensions': (
          'Template ads must be at least 10 pixels long and wide, and must not '
          'be outside the bounds of the slot, invalid given '
          'left/right/bottom/top/'),
  }

  SNIPPET_ERROR_TEMPLATE = 'HTML snippet for ad %d: %s'
  SNIPPET_ERROR_MESSAGES = {
      'click-url-missing': 'click url macros missing (CLICK_URL_UNESC or'
          ' CLICK_URL_ESC)',

  }
  ADSLOT_ERROR_TEMPLATE = 'Ad %d, adslot %d: %s'
  ADSLOT_ERROR_MESSAGES = {
      'zero-bid': '0 max CPM bid.',
      'zero-min-cpm': '0 min CPM bid',
      'min-more-than-max': 'min CPM >= max CPM',
      'invalid-slot-id': 'ad slot id is not present in the BidRequest.'
  }

  CLICK_URL_UNESC = 'http://www.google.com/url?sa=D&q='
  CLICK_URL_ESC = EscapeUrl(CLICK_URL_UNESC)
  CLICK_URL_UNESC_RE = re.compile('%%CLICK_URL_UNESC(:(.*?))?%%')
  CLICK_URL_ESC_RE = re.compile('%%CLICK_URL(_ESC){1,2}(:(.*?))?%%')
  CACHEBUSTER_RE = re.compile('%%CACHEBUSTER(:(.*?))?%%')
  SITE_RE = re.compile('%%SITE(:(.*?))?%%')
  WINNING_PRICE_RE = re.compile('%%WINNING_PRICE(:(.*?))?%%')
  WINNING_PRICE_ESC_RE = re.compile('%%WINNING_PRICE_ESC(:(.*?))?%%')

  WINNING_PRICE_RATIO = 0.33

  def __init__(self, logger):
    """Initializes a LogSummarizer.

    Args:
      logger: An iterable object containing Record instances.
    """
    self._logger = logger
    self._requests_sent = 0
    self._responses_ok = 0
    self._responses_successful_without_bids = 0
    self._processing_time_sum = 0
    self._processing_time_count = 0
    self._encrypted_price = None

    # Store records in the following buckets:
    # Good: the response can be parsed and no errors were detected.
    self._good = []
    # Problematic: the response can be parsed but has some problems.
    self._problematic = []
    # Invalid: the response can not be parsed.
    self._invalid = []
    # Error: the HTTP response had a non-200 response code.
    self._error = []

  def SetSampleEncryptedPrice(self, encrypted_price):
    """Sets the encrypted price to use for the ENCRYPTED_PRICE macro.

    Args:
      encrypted_price: A string with the encrypted price to return.
    """
    self._encrypted_price = encrypted_price

  def Summarize(self):
    """Collects and summarizes information from the logger."""
    for record in self._logger:
      self._requests_sent += 1
      if record.status == httplib.OK:
        self._responses_ok += 1
      else:
        # Responded with a non-OK code, don't to parse.
        record.problems.append(self.REQUEST_ERROR_MESSAGES['not-ok'])
        self._error.append(record)
        continue

      if not record.payload:
        record.problems.append(self.RESPONSE_ERROR_MESSAGES['empty'])
        self._invalid.append(record)
        # Empty response, don't try to parse.
        continue

      bid_response = realtime_bidding_pb2.BidResponse()
      try:
        bid_response.ParseFromString(record.payload)
      except google.protobuf.message.DecodeError:
        record.problems.append(self.RESPONSE_ERROR_MESSAGES['parse-error'])
        self._invalid.append(record)
        # Unparseable response, don't check its validity.
        continue

      if not bid_response.IsInitialized():
        # It parsed but the message is not initialized which means it's not
        # well-formed, consider this unparseable.
        record.problems.append(self.RESPONSE_ERROR_MESSAGES['uninitialized'])
        self._invalid.append(record)
        continue

      record.bid_response = bid_response

      if not bid_response.HasField('processing_time_ms'):
        record.problems.append(
            self.RESPONSE_ERROR_MESSAGES['no-processing-time'])
      else:
        self._processing_time_count += 1
        self._processing_time_sum += bid_response.processing_time_ms

      if record.bid_request.is_ping:
        self.ValidatePing(record)
      else:
        if not bid_response.ad:
          self._responses_successful_without_bids += 1
          self._good.append(record)
          continue
          # No ads returned, don't validate ads.

        for i, ad in enumerate(bid_response.ad):
          self.ValidateAd(ad, i, record)

      if record.problems:
        self._problematic.append(record)
      else:
        self._good.append(record)

  def ValidatePing(self, record):
    """Validates a response for a ping request.

    Args:
      record: A Record instance containing the context for this validation.
    """
    bid_response = record.bid_response
    if bid_response.ad:
      record.problems.append(self.RESPONSE_ERROR_MESSAGES['ads-in-ping'])

  def ValidateHtmlSnippetAd(self, ad, ad_index, record):
    """Validates a returned HTML 3rd party ad.

    The snippet must not be empty.
    Click through URL must be set and parse correctly.
    The BidRequest must not have a Video submessage, otherwise an instream video
    ad is required, not an HTML ad.

    Args:
      ad: A realtime_bidding_pb2.BidResponse_Ad instance.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.
    """
    if not ad.html_snippet:
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['empty-snippet']))

    self.ValidateClickThroughUrls(ad.click_through_url, ad_index, record)

    if record.bid_request.HasField('video'):
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['video-in-request']))

  def ValidateTemplateAd(self, ad, ad_index, record):
    """Validates a returned HTML 3rd party ad.

    Both the snippet_template and the template_parameter fields must be set.
    The length of template_parameter must match the number of parameters in
    snippet_template.
    The BidRequest must not have a Video submessage, otherwise an instream video
    ad is required, not an HTML ad.

    Args:
      ad: A realtime_bidding_pb2.BidResponse_Ad instance.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.
    """
    if not(ad.HasField('snippet_template') and
           len(ad.template_parameter) > 0):
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['template-and-parameters']))

    params = TEMPLATE_PARAM_REGEX.findall(ad.snippet_template)
    if len(params) < 2:
      record.problems.append(
          (self.AD_ERROR_TEMPLATE % (
              ad_index, self.AD_ERROR_MESSAGES['at-least-two-params']))
          + str(len(params)))
    if len(params) > 4:
      record.problems.append(
          (self.AD_ERROR_TEMPLATE % (
              ad_index, self.AD_ERROR_MESSAGES['at-most-four-params']))
          + str(len(params)))

    int_params = []  # Converted to integers.
    non_int_params = []  # Extracted strings of parameters that aren't ints.
    for i, param in enumerate(params):
      try:
        int_params.append(int(param))
      except ValueError:
        non_int_params.append(param)

    # Make sure the params are integers.
    if non_int_params:
      error_string = ', '.join(['%%%%%s%%%%' % p for p in non_int_params])
      record.problems.append((self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['non-int-params'])) + error_string)
    elif sorted(int_params) != range(len(int_params)):
      # Parameters in the template must be numbered 0..N-1, where N is the
      # number of parameters.
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['non-consecutive-params']))

    # Index of first backup parameter, initially -1 for none.
    backup_start = -1
    # How many non-backup ads do we have? Can be different than backup_start in
    # the case that we have a reguar ad after a backup ad.
    num_regular_params = 0
    for i, param_value in enumerate(ad.template_parameter):
      if param_value.HasField('backup_index'):
        if backup_start < 0:
          backup_start = i

        backup_index = param_value.backup_index
        # Backup parameters must reference a valid index.
        if backup_index < 0 or backup_index >= len(int_params):
          record.problems.append((self.AD_ERROR_TEMPLATE % (
              ad_index, self.AD_ERROR_MESSAGES['invalid-backup-reference'])) +
              str(backup_index))
      else:
        num_regular_params += 1
        if backup_start != -1:
          # We encountered a regular ad after a backup ad.
          record.problems.append(self.AD_ERROR_TEMPLATE % (
              ad_index, self.AD_ERROR_MESSAGES['backup-not-at-end']))

    if num_regular_params != len(params):
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['param-mismatch']))

    if ad.HasField('buyer_creative_id'):
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['buyer-id-in-response']))
    if ad.click_through_url:
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['url-in-response']))

    # Find slot dimension.
    width, height = None, None
    if ad.adslot:
      # Assume there's only one adslot.
      adslot = self.FindAdSlotInRequest(ad.adslot[0].id, record.bid_request)
      if adslot.width and adslot.height:
        width = adslot.width[0]
        height = adslot.height[0]

    for i, param_value in enumerate(ad.template_parameter):
      if not param_value.HasField('buyer_creative_id'):
        record.problems.append(self.AD_ERROR_TEMPLATE % (
            ad_index, self.AD_ERROR_MESSAGES['no-id-in-parameter']))
      if not param_value.HasField('parameter_value'):
        record.problems.append(self.AD_ERROR_TEMPLATE % (
            ad_index, self.AD_ERROR_MESSAGES['no-value-in-parameter']))

      self.ValidateClickThroughUrls([param_value.click_through_url],
                                    ad_index,
                                    record)

      if not(param_value.HasField('left') and
             param_value.HasField('right') and
             param_value.HasField('bottom') and
             param_value.HasField('top')):
        record.problems.append(self.AD_ERROR_TEMPLATE % (
            ad_index, self.AD_ERROR_MESSAGES['no-bounds']))
      elif (width and height and
            (param_value.left < 0 or param_value.right > width
             or param_value.top > height or param_value.bottom < 0
             or param_value.right - param_value.left < 10
             or param_value.top - param_value.bottom < 10)):
        record.problems.append(
            (self.AD_ERROR_TEMPLATE % (
                ad_index,
                self.AD_ERROR_MESSAGES['invalid-template-dimensions'])) +
            ('%d/%d/%d/%d.' % (param_value.left, param_value.right,
                               param_value.bottom, param_value.top)))
      elif not param_value.HasField('backup_index'):
        for other_param in ad.template_parameter[:i]:
          if other_param.HasField('backup_index'):
            continue
          if param_value.right <= other_param.left:
            continue
          if other_param.right <= param_value.left:
            continue
          if param_value.bottom >= other_param.top:
            continue
          if other_param.bottom >= param_value.top:
            continue
          record.problems.append(self.AD_ERROR_TEMPLATE % (
              ad_index, self.AD_ERROR_MESSAGES['one-dimension']))
          break

    if record.bid_request.HasField('video'):
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['video-in-request']))

  def ValidateClickThroughUrls(self, click_through_urls, ad_index, record):
    """Validates click through URLs for an ad.

    There must be at least one URL, and it must parse.

    Args:
      click_through_urls: A list of urls.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.
    """
    if not click_through_urls:
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['no-click-through-urls']))
    for click_through_url in click_through_urls:
      parsed_url = urlparse.urlparse(click_through_url)
      # Must have scheme and netloc.
      if not (parsed_url[0]
              and (parsed_url[0] == 'http' or parsed_url[0] == 'https')
              and parsed_url[1]):
        record.problems.append(
            (self.AD_ERROR_TEMPLATE % (ad_index,
                                       self.AD_ERROR_MESSAGES['invalid-url'])) +
            click_through_url)

  def ValidateInstreamVideoAd(self, ad, ad_index, record):
    """Validates a returned instream video ad.

    The video URL must parse and be valid.
    The BidRequest must have a Video submessage, otherwise returning an instream
    video ad is invalid.

    Args:
      ad: A realtime_bidding_pb2.BidResponse_Ad instance.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.
    """
    parsed_url = urlparse.urlparse(ad.video_url)
    if not (parsed_url[0] and
            (parsed_url[0] == 'http' or parsed_url[0] == 'https') and
            parsed_url[1]):
      record.problems.append(
          (self.AD_ERROR_TEMPLATE % (
              ad_index, self.AD_ERROR_MESSAGES['invalid-video-url']))
          + ad.video_url)

    if not record.bid_request.HasField('video'):
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['no-video-in-request']))

  def ValidateAd(self, ad, ad_index, record):
    """Validates a returned ad.

    Args:
      ad: A realtime_bidding_pb2.BidResponse_Ad instance.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.
    """
    ad_type_fields = [
        'html_snippet', 'video_url', 'snippet_template']
    found_types = []

    for field in ad_type_fields:
      if ad.HasField(field):
        found_types.append(field)

    if not found_types:
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['no-types']))
    elif len(found_types) > 1:
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['mulitple-types']))

    if ad.HasField('video_url'):
      self.ValidateInstreamVideoAd(ad, ad_index, record)

    if ad.HasField('html_snippet'):
      self.ValidateHtmlSnippetAd(ad, ad_index, record)

    if ad.HasField('snippet_template') or len(ad.template_parameter):
      self.ValidateTemplateAd(ad, ad_index, record)

    if not ad.adslot:
      record.problems.append(self.AD_ERROR_TEMPLATE % (
          ad_index, self.AD_ERROR_MESSAGES['no-adslots']))
      self._responses_successful_without_bids += 1

    adslot_problems = False
    for adslot_index, adslot in enumerate(ad.adslot):
      adslot_problems = (adslot_problems or
                         self.ValidateAdSlot(adslot, ad_index, adslot_index,
                                             record))
    # Only validate snippets if all adslots are valid and there's a snippet.
    if ad.HasField('html_snippet') and ad.html_snippet and not adslot_problems:
      self.ValidateHtmlSnippet(ad, ad_index, record)

  def ValidateHtmlSnippet(self, ad, ad_index, record):
    """Validates a returned HTML snippet, including macro substitution.

    The winning price macro is substituted with an unencrypted value for the
    purpose of initial testing.

    This method assumes that all adslots in the ad are valid and that the ad
    has an HTML snippet

    Args:
      ad: A realtime_bidding_pb2.BidResponse_Ad instance.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.
    """
    if not ad.adslot:
      return

    # Check that one of the required click url macros is present.
    if not (re.search(self.CLICK_URL_ESC_RE, ad.html_snippet) or
            re.search(self.CLICK_URL_UNESC_RE, ad.html_snippet)):
      record.problems.append(self.SNIPPET_ERROR_TEMPLATE % (
          ad_index, self.SNIPPET_ERROR_MESSAGES['click-url-missing']))

    adslot_id = ad.adslot[0].id

    width, height = 0, 0
    for adslot in record.bid_request.adslot:
      if adslot.id == adslot_id:
        if adslot.width:
          width = adslot.width[0]
        if adslot.height:
          height = adslot.height[0]

    if not height or not width:
      # Could not find the corresponding request adslot, invalid response.
      return

    # Substitute click string macros.
    html_snippet = re.sub(self.CLICK_URL_UNESC_RE,
                          self.CLICK_URL_UNESC,
                          ad.html_snippet)
    html_snippet = re.sub(self.CLICK_URL_ESC_RE,
                          self.CLICK_URL_ESC,
                          html_snippet)

    # Winning price notification is in CPI, not CPM.
    winning_price = (ad.adslot[0].max_cpm_micros * self.WINNING_PRICE_RATIO
                     / 1000)

    # Substitute winning price.
    if (self._encrypted_price):
      html_snippet = re.sub(self.WINNING_PRICE_RE,
                            self._encrypted_price,
                            html_snippet)
      html_snippet = re.sub(self.WINNING_PRICE_ESC_RE,
                            EscapeUrl(self._encrypted_price),
                            html_snippet)
    else:
      html_snippet = re.sub(self.WINNING_PRICE_RE,
                            str(winning_price),
                            html_snippet)
      html_snippet = re.sub(self.WINNING_PRICE_ESC_RE,
                            str(winning_price),
                            html_snippet)

    # Substitute cache buster macro.
    random.seed()
    cachebuster = random.randint(0, sys.maxint)
    html_snippet = re.sub(self.CACHEBUSTER_RE,
                          str(cachebuster),
                          html_snippet)

    # Substitute the site.
    parsed_url = urlparse.urlparse(record.bid_request.url)
    netloc = parsed_url[1]
    if netloc:
      domain = netloc
      if ':' in netloc:
        domain = netloc[0:netloc.rfind(':')]
      html_snippet = re.sub(self.SITE_RE,
                            EscapeUrl(domain),
                            html_snippet)

    record.html_snippets[ad_index] = html_snippet

  def FindAdSlotInRequest(self, adslot_id, bid_request):
    """Returns the adslot with the given id from the bid request.

    Args:
      adslot_id: The id of an adslot.
      bid_request: A realtime_bidding_pb2.BidRequest instance.

    Returns:
      A realtime_bidding_pb2.BidRequest_AdSlot or None if a matching adslot
      could not be found.
    """
    for request_adslot in bid_request.adslot:
      if request_adslot.id == adslot_id:
        return request_adslot
    return None

  def ValidateAdSlot(self, adslot, ad_index, adslot_index, record):
    """Validates a returned ad slot.

    Args:
      adslot: A realtime_bidding_pb2.BidResponse_Ad_AdSlot instance.
      ad_index: The index of the ad in the BidResponse, used to make error
          messages more informative.
      adslot_index: The index of the adslot in the ad, used to make error
          messages more informative.
      record: A Record instance containing the context for this validation.

    Returns:
      True if any problems were found with the adslot.
    """
    problems_found = False
    if adslot.max_cpm_micros == 0:
      record.problems.append(self.ADSLOT_ERROR_TEMPLATE % (
          adslot_index, ad_index, self.ADSLOT_ERROR_MESSAGES['zero-bid']))
      problems_found = True

    if adslot.HasField('min_cpm_micros'):
      if adslot.min_cpm_micros == 0:
        record.problems.append(self.ADSLOT_ERROR_TEMPLATE % (
            adslot_index,
            ad_index,
            self.ADSLOT_ERROR_MESSAGES['zero-min-cpm']))
        problems_found = True
      elif adslot.min_cpm_micros >= adslot.max_cpm_micros:
        record.problems.append(self.ADSLOT_ERROR_TEMPLATE % (
            adslot_index,
            ad_index,
            self.ADSLOT_ERROR_MESSAGES['min-more-than-max']))
        problems_found = True

    request_adslot = self.FindAdSlotInRequest(adslot.id, record.bid_request)
    if not request_adslot:
      record.problems.append(self.ADSLOT_ERROR_TEMPLATE % (
          ad_index,
          adslot_index,
          self.ADSLOT_ERROR_MESSAGES['invalid-slot-id']))
      problems_found = True

    return problems_found

  def WriteLogFiles(self, good_log, problematic_log, invalid_log, error_log,
                    snippet_log):
    """Writes log files for successful/error/problematic/invalid requests.

    Args:
      good_log: A file like object for writing the log of good requests, will
          not be closed by LogSummarizer.
      problematic_log: A file like object for writing the log of problematic
          requests, will not be closed by LogSummarizer.
      invalid_log: A file like object for writing the log of invalid requests,
          will not be closed by LogSummarizer.
      error_log: A file like object for writing the log of error requests, will
          not be closed by LogSummarizer.
      snippet_log: A file like object for writing the rendered snippets, will
          not be closed by LogSummarizer.
    """
    # Write header into snippet log file.
    if self._good or self._problematic:
      snippet_log.write('<html><head><title>Rendered snippets</title></head>\n')
      snippet_log.write('<body><h1>Rendered Snippets</h1>')
      snippet_log.write('<p>Your server has returned the following renderable'
                        ' snippets:</p>')
      snippet_log.write('<ul>')

    if self._problematic:
      problematic_log.write('=== Responses that parsed but had problems ===\n')
    for record in self._problematic:
      problematic_log.write('BidRequest:\n')
      problematic_log.write(str(record.bid_request))
      problematic_log.write('\nBidResponse:\n')
      problematic_log.write(str(record.bid_response))
      problematic_log.write('\nProblems:\n')
      for problem in record.problems:
        problematic_log.write('\t%s\n' % problem)
      self.WriteSnippet(record, snippet_log)

    if self._good:
      good_log.write('=== Successful responses ===\n')
    for record in self._good:
      good_log.write('BidRequest:\n')
      good_log.write(str(record.bid_request))
      good_log.write('\nBidResponse:\n')
      good_log.write(str(record.bid_response))
      self.WriteSnippet(record, snippet_log)

    if self._good or self._problematic:
      # Write footer into snippet log file.
      snippet_log.write('</ul></body></html>')

    if self._invalid:
      invalid_log.write('=== Responses that failed to parse ===\n')
    for record in self._invalid:
      invalid_log.write('BidRequest:\n')
      invalid_log.write(str(record.bid_request))
      invalid_log.write('\nPayload represented as a python list of bytes:\n')
      byte_list = [ord(c) for c in record.payload]
      invalid_log.write(str(byte_list))

    if self._error:
      error_log.write('=== Requests that received a non 200 HTTP response'
                      ' ===\n')
    for record in self._error:
      error_log.write('BidRequest:\n')
      error_log.write(str(record.bid_request))
      error_log.write('HTTP response status code: %d\n' % record.status)
      error_log.write('\nPayload represented as a python list of bytes:\n')
      byte_list = [ord(c) for c in record.payload]
      error_log.write(str(byte_list))

  def WriteSnippet(self, record, log):
    """Writes the snippets in the given record into the log."""
    if not record.html_snippets:
      # No snippets to print. Records that are problematic may or may not have
      # snippets.
      return

    for ad_index, snippet in record.html_snippets.iteritems():
      response_adslot_id = record.bid_response.ad[ad_index].adslot[0].id
      request_adslot = self.FindAdSlotInRequest(response_adslot_id,
                                                record.bid_request)
      if request_adslot is None:
        continue
      log.write('<li>')
      log.write('<h3>Bid Request</h3>')
      log.write('<pre>%s</pre>' % cgi.escape(str(record.bid_request)))
      log.write('<h3>Bid Response</h3>')
      log.write('<pre>%s</pre>' % cgi.escape(str(record.bid_response)))
      log.write('<h3>Rendered Snippet</h3>')

      iframe = ('<iframe src="data:text/html;base64,\n%s" '
                'width=%d height=%d scrolling=no marginwidth=0 '
                'marginheight=0></iframe>\n' % (
                    base64.b64encode(snippet),
                    request_adslot.width[0],
                    request_adslot.height[0]))
      log.write(iframe)
      log.write('</li>')

  def PrintReport(self):
    """Prints a summary report."""
    print '=== Summary of Real-time Bidding test ==='
    print 'Requests sent: %d' % self._requests_sent
    print 'Responses with a 200/OK HTTP response code: %d' % self._responses_ok
    print 'Responses with a non-200 HTTP response code: %d' % len(self._error)
    print 'Good responses (no problems found): %d' % len(self._good)
    print 'Invalid (unparseable) with a 200/OK HTTP response code: %d' % len(
        self._invalid)
    print 'Parseable responses with problems: %d' % len(self._problematic)
    if self._processing_time_count:
      print 'Average processing time in milliseconds %d' % (
          self._processing_time_sum * 1.0 / self._processing_time_count)
    if self._responses_successful_without_bids == self._requests_sent:
      print 'ERROR: None of the responses had bids!'
