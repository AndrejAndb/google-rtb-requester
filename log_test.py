#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.
"""Unit tests for log.py"""

import re
import StringIO
import unittest

import log
import realtime_bidding_pb2


class LoggerTest(unittest.TestCase):
  """Tests the log.Logger class."""

  def setUp(self):
    self.logger = log.Logger()

  def Iterate(self):
    """Iterates over the items in the logger.

    Returns:
      Log items as a list.
    """
    log_items = [a for a in self.logger]
    return log_items

  def testLogSynchronousRequest(self):
    """Tests logging a request/response synchronously."""
    self.assertEqual(0, len(self.logger._records))
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id111'
    self.logger.LogSynchronousRequest(bid_request, 200, 'Hello')
    self.assertEqual(1, len(self.logger._records))
    self.assertEqual(bid_request, self.logger._records[0].bid_request)
    self.assertEqual(200, self.logger._records[0].status)
    self.assertEqual('Hello', self.logger._records[0].payload)
    self.assertFalse(self.logger._done)

  def testSetDone(self):
    """Tests locking the logger."""
    self.assertFalse(self.logger._done)
    self.logger.Done()
    self.assertTrue(self.logger._done)
    # Idempotence.
    self.logger.Done()
    self.assertTrue(self.logger._done)

  def testIteratingBeforeDone(self):
    """Tests that iterating before calling Done raises a LoggerException."""
    self.assertRaises(log.LoggerException, self.Iterate)
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id113'
    self.logger.LogSynchronousRequest(bid_request, 123, 'Payload')
    self.assertRaises(log.LoggerException, self.Iterate)

  def testLoggingAfterDone(self):
    """Tests that logging after calling Done raises a LoggerException."""
    bid_request = realtime_bidding_pb2.BidRequest()

    self.logger.Done()

    self.assertFalse(self.logger.LogSynchronousRequest(bid_request, 200,
                                                       'payload'))

  def testIteratingAfterDoneWithoutLogRecords(self):
    """Tests iterating over an empty locked logger."""
    self.logger.Done()
    records = [record for record in self.logger]
    self.assertEqual([], records)

  def testIterationAfterDoneWithLogRecords(self):
    """Test iterating over a locked logger with records."""
    for i in range(10):
      bid_request = realtime_bidding_pb2.BidRequest()
      bid_request.id = 'id11%d' % i
      self.logger.LogSynchronousRequest(bid_request, 123, 'Payload')
    self.logger.Done()
    records = [record for record in self.logger]
    self.assertEqual(10, len(records))
    for record in records:
      self.assertTrue(record.bid_request.HasField('id'))
      self.assertEqual(123, record.status)
      self.assertEqual('Payload', record.payload)

  def testIsDone(self):
    """Tests checking whether the logger has been locked for updates."""
    self.assertFalse(self.logger.IsDone())
    self.logger.Done()
    self.assertTrue(self.logger.IsDone())


class TestLogSummarizer(unittest.TestCase):
  def setUp(self):
    """Sets up tests."""
    self.records = []

  def CheckNInvalidResponses(self, n):
    """Checks that n invalid resonses were processed.

    Args:
      n - the number of expected invalid responses."""
    self.assertEquals(n, self.summarizer._requests_sent)
    self.assertEquals(n, self.summarizer._responses_ok)
    self.assertEquals(n, self.summarizer._responses_ok)
    self.assertEquals(0, self.summarizer._responses_successful_without_bids)
    self.assertEquals(0, self.summarizer._processing_time_count)
    self.assertEquals(0, self.summarizer._processing_time_sum)
    self.assertEquals(0, len(self.summarizer._good))
    self.assertEquals(0, len(self.summarizer._problematic))
    self.assertEquals(0, len(self.summarizer._error))
    self.assertEquals(n, len(self.summarizer._invalid))

  def CheckNProblematicResponses(self, n, no_bids=0):
    """Checks that n problematic requests have been summarized.

    Args:
      n - the number of good requests/responses to expect.
      no_bids - the number of expected responses with no bids.
    """
    self.assertEquals(n, self.summarizer._requests_sent)
    self.assertEquals(n, self.summarizer._responses_ok)
    self.assertEquals(no_bids,
                      self.summarizer._responses_successful_without_bids)
    self.assertEquals(0, len(self.summarizer._good))
    self.assertEquals(n, len(self.summarizer._problematic))
    self.assertEquals(0, len(self.summarizer._invalid))
    self.assertEquals(0, len(self.summarizer._error))

  def CheckNGoodRequests(self, n, no_bids=0):
    """Checks that n good requests have been summarized.

    Args:
      n - the number of good requests/responses to expect.
      no_bids - the number of expected responses with no bids.
    """
    self.assertEquals(n, self.summarizer._requests_sent)
    self.assertEquals(n, self.summarizer._responses_ok)
    self.assertEquals(no_bids,
                      self.summarizer._responses_successful_without_bids)
    expected_sum = 0
    if self.records:
      for record in self.records:
        if hasattr(record, 'bid_response'):
          expected_sum += record.bid_response.processing_time_ms
    self.assertEquals(expected_sum, self.summarizer._processing_time_sum)
    self.assertEquals(n, self.summarizer._processing_time_count)
    self.assertEquals(n, len(self.summarizer._good))
    self.assertEquals(0, len(self.summarizer._problematic))
    self.assertEquals(0, len(self.summarizer._invalid))
    self.assertEquals(0, len(self.summarizer._error))

  def CreateSuccessfulRecord(self):
    """Returns a Record with a successful request/response pair.

    Returns:
      A (BidResopnse, Record) pair. The bid_response is returned for
      convenience so a test method can make a slight modification and serialize
      it into record.bid_response without parsing record.bid_response first.
    """
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id111'
    request_adslot = bid_request.adslot.add()
    request_adslot.id = 123
    request_adslot.height.append(468)
    request_adslot.width.append(60)
    status = 200
    bid_response = realtime_bidding_pb2.BidResponse()
    bid_response.processing_time_ms = 10
    ad = bid_response.ad.add()
    ad.click_through_url.append('http://url.com')
    ad.html_snippet = ('A snippet. <a href=\'%%CLICK_URL_UNESC%%'
                       'http://www.google.com\'>link</a>')
    adslot = ad.adslot.add()
    adslot.id = 123
    adslot.max_cpm_micros = 5000000
    record = log.Record(bid_request, status, bid_response.SerializeToString())
    return bid_response, record

  def CreateSuccessfulTemplateRecord(self):
    """Returns a Record with a successful request/response for a template ad.

    Returns:
      A (BidResopnse, Record) pair. The bid_response is returned for
      convenience so a test method can make a slight modification and serialize
      it into record.bid_response without parsing record.bid_response first.
    """
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id111'
    request_adslot = bid_request.adslot.add()
    request_adslot.id = 123
    request_adslot.height.append(468)
    request_adslot.width.append(60)
    status = 200
    bid_response = realtime_bidding_pb2.BidResponse()
    bid_response.processing_time_ms = 10
    ad = bid_response.ad.add()
    ad.snippet_template = 'Template %%P0%%, %%P1%%.'
    param = ad.template_parameter.add()
    param.parameter_value = 'value0'
    param.left = 1
    param.right = 15
    param.top = 20
    param.bottom = 1
    param.click_through_url = 'http://url1.com'
    param.buyer_creative_id = '12345'
    param = ad.template_parameter.add()
    param.parameter_value = 'value1'
    param.left = 1
    param.right = 15
    param.top = 35
    param.bottom = 21
    param.click_through_url = 'http://url2.com'
    param.buyer_creative_id = '54321'
    adslot = ad.adslot.add()
    adslot.id = 123
    adslot.max_cpm_micros = 5000000
    record = log.Record(bid_request, status, bid_response.SerializeToString())
    return bid_response, record

  def CreateSuccessfulVideoRecord(self):
    """Returns a Record with a successful video request/response pair.

    Returns:
      A (BidResopnse, Record) pair. The bid_response is returned for
      convenience so a test method can make a slight modification and serialize
      it into record.bid_response without parsing record.bid_response first.
    """
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id111'
    bid_request.video.videoad_start_delay = 1000
    request_adslot = bid_request.adslot.add()
    request_adslot.id = 123
    status = 200
    bid_response = realtime_bidding_pb2.BidResponse()
    bid_response.processing_time_ms = 10
    ad = bid_response.ad.add()
    ad.click_through_url.append('http://url.com')
    ad.video_url = 'http://my.video.url.com'
    adslot = ad.adslot.add()
    adslot.id = 123
    adslot.max_cpm_micros = 5000000
    record = log.Record(bid_request, status, bid_response.SerializeToString())
    return bid_response, record

  def testInit(self):
    """Tests that isntance variables are initialized."""
    self.summarizer = log.LogSummarizer(self.records)
    self.CheckNGoodRequests(0)

  def testSummarizeEmpty(self):
    """Tests summarizing an empty list."""
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(0)

  def SetupLogs(self):
    """Sets up StringIO objects as mock open log files."""
    self.error_log = StringIO.StringIO()
    self.invalid_log = StringIO.StringIO()
    self.good_log = StringIO.StringIO()
    self.problematic_log = StringIO.StringIO()
    self.snippet_log = StringIO.StringIO()

  def testSummarizeWithGoodRecord(self):
    """Tests summarizing with one good record."""
    bid_response, record = self.CreateSuccessfulRecord()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeWithGoodVideoAdRecord(self):
    """Tests summarizing with one good record."""
    _, record = self.CreateSuccessfulVideoRecord()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeManyGoodRecords(self):
    """Tests summarizing with multiple good records."""
    for _ in range(10):
      _, record = self.CreateSuccessfulRecord()
      self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(10)
    for record in self.records:
      self.assertTrue(record in self.summarizer._good)
      self.assertEqual(0, len(record.problems))

  def testSummarizeEmptyResonse(self):
    """Tests summarizing with multiple good records."""
    _, record = self.CreateSuccessfulRecord()
    record.payload = ""
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNInvalidResponses(1)
    self.assertTrue(record in self.summarizer._invalid)
    self.assertEqual(1, len(record.problems))

  def testSummarizeUnparseableResonse(self):
    """Tests summarizing with multiple good records."""
    _, record = self.CreateSuccessfulRecord()
    record.payload = 'garbage'
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNInvalidResponses(1)
    self.assertTrue(record in self.summarizer._invalid)
    self.assertEqual(1, len(record.problems))

  def testSummarizeNonOkHttpStatus(self):
    """Tests summarizing a response with a non-200 HTTP status."""
    _, record = self.CreateSuccessfulRecord()
    record.status = 404
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.assertEqual(0, self.summarizer._responses_ok)
    self.assertEqual(1, len(self.summarizer._error))
    self.assertTrue(record in self.summarizer._error)
    self.assertEqual(1, len(record.problems))

  def testSummarizeWithoutProcessingTime(self):
    """Tests that lack of processing time generates an error message."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ClearField('processing_time_ms')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeWithoutAds(self):
    """Tests that lack of ads is considered a valid response."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ClearField('ad')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1, no_bids=1)
    self.assertTrue(record in self.summarizer._good)

  def testSummarizeSnippetAndVideo(self):
    """Tests summarizing an ad with both a video url and an HTML snippet."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].video_url = 'http://video.com'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    # One error for both types of ads in a repsonse, another for a video
    # response when the bid request didn't contain a Video element.
    self.assertEqual(2, len(record.problems))

  def testSummarizeSnippetAndTemplate(self):
    """Tests summarizing an ad with both a template ad and an HTML snippet."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].html_snippet = (
        'A snippet. <a href=\'%%CLICK_URL_UNESC%%'
        'http://www.google.com\'>link</a>')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    # One error for both types of ads in a response, another for
    # click_through_url missing for HTML snippet ad.
    self.assertEqual(2, len(record.problems))

  def testSummarizeInvalidVideoUrl(self):
    """Tests summarizing an invalid video url."""
    bid_response, record = self.CreateSuccessfulVideoRecord()
    bid_response.ad[0].video_url = 'invalid video url'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeNoSnippet(self):
    """Tests summarizing an ad without an HTML snippet."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].ClearField('html_snippet')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeEmptySnippet(self):
    """Tests summarizing an ad with an empty HTML snippet."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].html_snippet = ""
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeMissingClickMacros(self):
    """Tests summarizing an ad with a snippet missing the click url macros."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].html_snippet = 'No click url macro.'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeHasEscapedClickMacro(self):
    """Tests summarizing when a snippet has the escaped click url macro."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].html_snippet = '%%CLICK_URL_ESC%%'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeHasDoubleEscapedClickMacro(self):
    """Tests summarizing when a snippet has an ESC_ESC click url macro."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].html_snippet = '%%CLICK_URL_ESC_ESC%%'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeHasUnescapedClickMacro(self):
    """Tests summarizing when a snippet has the unescaped click url macro."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].html_snippet = '%%CLICK_URL_UNESC%%'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testValidateHtmlSnippetSubstitutions(self):
    """Tests that ValidateHtmlSnippet does correct macro substitutions."""
    snippet = ('%%CLICK_URL_UNESC%%\n'
               '%%CLICK_URL_ESC%%\n'
               '%%CLICK_URL_ESC_ESC%%\n'
               '%%SITE%%\n'
               '%%CACHEBUSTER%%\n'
               '%%WINNING_PRICE%%\n'
               '%%WINNING_PRICE_ESC%%\n')
    bid_response, record = self.CreateSuccessfulRecord()
    record.bid_request.url = 'http://some.url.com/page?q=v'
    bid_response.ad[0].html_snippet = snippet
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.ValidateHtmlSnippet(bid_response.ad[0], 0,  # ad index
                                        record)
    self.assertEqual(0, len(record.problems))
    self.assertTrue(0 in record.html_snippets)
    substituted_snippet = record.html_snippets[0]
    pattern_str = '%s\n%s\n%s\n%s\n%s\n%s\n%s\n' % (
        re.escape(log.LogSummarizer.CLICK_URL_UNESC),
        re.escape(log.LogSummarizer.CLICK_URL_ESC),
        re.escape(log.LogSummarizer.CLICK_URL_ESC),
        re.escape('some.url.com'),  # The domain we set in the request.
        '\d+',  # Cachebuster.
        '[\d\.]+',  # Winning price.
        '[\d\.]+',  # Winning price.
    )
    pattern_obj = re.compile(pattern_str, re.MULTILINE)
    self.assertFalse(pattern_obj.match(substituted_snippet) is None)

  def testSummarizeNoAdSlot(self):
    """Tests summarizing an ad without any ad slots."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].ClearField('adslot')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1, no_bids=1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeHttpsClickThroughUrl(self):
    """Tests summarizing an ad without any click through urls."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].ClearField('click_through_url')
    bid_response.ad[0].click_through_url.append('https://url.com')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeNoClickThroughUrl(self):
    """Tests summarizing an ad without any click through urls."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].ClearField('click_through_url')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeClickThroughUrlWithoutScheme(self):
    """Tests summarizing an ad with a click through url without a scheme."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].click_through_url[0] = 'invalidurl'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeClickThroughUrlInvalidScheme(self):
    """Tests summarizing an ad with a click through url with an invalid scheme.
    """
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].click_through_url[0] = 'invalid://url'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeClickThroughUrlWithoutHost(self):
    """Tests summarizing an ad with a click through url without a host name."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].click_through_url[0] = 'http://'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeEmptyClickThroughUrl(self):
    """Tests summarizing an ad with an empty click through url."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].click_through_url[0] = ""
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeZeroMaxCpm(self):
    """Tests summarizing an adslot with zero max CPM."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].adslot[0].max_cpm_micros = 0
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeZeroMinCpm(self):
    """Tests summarizing an adslot with zero min CPM."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].adslot[0].min_cpm_micros = 0
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizePingRequest(self):
    """Tests summarizing a ping request."""
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id111'
    bid_request.is_ping = True
    bid_response = realtime_bidding_pb2.BidResponse()
    bid_response.processing_time_ms = 0
    record = log.Record(bid_request, 200, bid_response.SerializeToString())
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)

  def testSummarizePingRequestHasAds(self):
    """Tests summarizing a ping request for which ads are returned."""
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = 'id111'
    bid_request.is_ping = True

    _, record = self.CreateSuccessfulRecord()
    record.bid_request = bid_request
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)

  def testSummarizeMinCpmExceedsMaxCpm(self):
    """Tests summarizing an adslot with min CPM > max CPM."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].adslot[0].max_cpm_micros = 100000
    bid_response.ad[0].adslot[0].min_cpm_micros = 100000
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeInvalidAdSlot(self):
    """Tests summarizing an adslot with an invalid id."""
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].adslot[0].id = record.bid_request.adslot[0].id + 1
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeOneGoodTemplateAd(self):
    """Tests summarizing a response with one template ad."""
    _, record = self.CreateSuccessfulTemplateRecord()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeOneGoodTemplateAdWithBackups(self):
    """Tests summarizing a response with one template ad with backups."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    backup = bid_response.ad[0].template_parameter.add()
    backup.MergeFrom(bid_response.ad[0].template_parameter[0])
    backup.buyer_creative_id = 'backup1'
    backup.click_through_url = 'http://url3.com'
    backup.backup_index = 0
    backup = bid_response.ad[0].template_parameter.add()
    backup.MergeFrom(bid_response.ad[0].template_parameter[1])
    backup.buyer_creative_id = 'backup1'
    backup.click_through_url = 'http://url3.com'
    backup.backup_index = 1
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNGoodRequests(1)
    self.assertTrue(record in self.summarizer._good)
    self.assertEqual(0, len(record.problems))

  def testSummarizeTemplateWithNoParameterValues(self):
    """Tests summarizing a template ad missing the parameters."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].ClearField('template_parameter')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    # One error for no parameters, one error for mismatched number of parameters
    # in the template and parameter values.
    self.assertEqual(2, len(record.problems))

  def testSummarizeTemplateWithNotEnoughParameters(self):
    """Tests summarizing a template ad with < 2 parameters in the template."""
    for i in range(2):
      bid_response, record = self.CreateSuccessfulTemplateRecord()
      template = 'no params'
      for param in range(i):
        template += 'param %%%%P%d%%%% ' % param
      bid_response.ad[0].snippet_template = template
      record.payload = bid_response.SerializeToString()
      self.records = [record]
      self.summarizer = log.LogSummarizer(self.records)
      self.summarizer.Summarize()
      self.CheckNProblematicResponses(1)
      self.assertTrue(record in self.summarizer._problematic)
      # One error for no parameters in the template, one error for mismatched
      # number of parameters in the template and parameter values.
      self.assertEqual(2, len(record.problems))

  def testSummarizeTemplateWithTooManyParameters(self):
    """Tests summarizing a template ad > 4 parameters in the template."""
    for i in [5, 6, 10]:
      bid_response, record = self.CreateSuccessfulTemplateRecord()
      template = 'no params'
      for param in range(i):
        template += 'param %%%%P%d%%%% ' % param
      bid_response.ad[0].snippet_template = template
      record.payload = bid_response.SerializeToString()
      self.records = [record]
      self.summarizer = log.LogSummarizer(self.records)
      self.summarizer.Summarize()
      self.CheckNProblematicResponses(1)
      self.assertTrue(record in self.summarizer._problematic)
      # One error for no parameters in the template, one error for mismatched
      # number of parameters in the template and parameter values.
      self.assertEqual(2, len(record.problems))

  def testSummarizeTemplateWithNonIntParameters(self):
    """Tests summarizing a template ad with non-integer parameters."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].snippet_template = 'Bad %%Px%% and %%Py%% params!'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateWithParameterMismatch(self):
    """Tests summarizing a template ad with mismatched parameters."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].snippet_template = '%%P0%%, %%P1%% and %%P2%%!'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateWithMisnumberedParameters(self):
    """Tests summarizing a template ad with non-consecutive parameters."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].snippet_template = 'Two %%P0%% params %%P2%%!'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateWithAdsAfterBackups(self):
    """Tests summarizing a template ad with regular ads after backup ads ."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].snippet_template = '%%P0%% params %%P1%% and %%P2%%!'
    backup = bid_response.ad[0].template_parameter.add()
    backup.MergeFrom(bid_response.ad[0].template_parameter[0])
    backup.backup_index = 0
    param2 = bid_response.ad[0].template_parameter.add()
    param2.parameter_value = 'value2'
    param2.left = 1
    param2.right = 15
    param2.top = 50
    param2.bottom = 36
    param2.click_through_url = 'http://url3.com'
    param2.buyer_creative_id = '54321789'

    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateInvalidBackupIndex(self):
    """Tests summarizing a template ad an invalid backup index.."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].snippet_template = '%%P0%% params %%P1%%!'
    backup = bid_response.ad[0].template_parameter.add()
    backup.MergeFrom(bid_response.ad[0].template_parameter[0])
    backup.backup_index = 2  # We only have index 0 and 1.

    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateMissingParameterValue(self):
    """Tests summarizing a template ad missing a parameter_value."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].template_parameter[0].ClearField('parameter_value')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateWithBuyerCreativeIdInAd(self):
    """Tests summarizing a template ad a buyer_creative_id in the parent."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].buyer_creative_id = '123'
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateMissingBuyerCreativeId(self):
    """Tests summarizing a template ad missing a buyer_creative_id."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].template_parameter[0].ClearField('buyer_creative_id')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateWithClickThroughUrlInAd(self):
    """Tests summarizing a template ad with landing page url in the parent."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].click_through_url.append('http://url.com')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateMissingClickThroughUrl(self):
    """Tests summarizing a template ad missing a landing page url."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    bid_response.ad[0].template_parameter[0].ClearField('click_through_url')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateMissingBounds(self):
    """Tests summarizing a template ad with missing bounds."""
    for field_name in ['left', 'right', 'top', 'bottom']:
      bid_response, record = self.CreateSuccessfulTemplateRecord()
      bid_response.ad[0].template_parameter[0].ClearField(field_name)
      record.payload = bid_response.SerializeToString()
      self.records = [record]
      self.summarizer = log.LogSummarizer(self.records)
      self.summarizer.Summarize()
      self.CheckNProblematicResponses(1)
      self.assertTrue(record in self.summarizer._problematic)
      self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateBadBoundsBounds(self):
    """Tests summarizing a template ad with a missing left bound."""
    # A variety of invalid bounds.
    bad_bounds_list = [
        # Left < 0.
        {'left': -1, 'right': 15, 'top': 15, 'bottom': 0},
        # Right > slot width.
        {'left': 1, 'right': 100, 'top': 15, 'bottom': 0},
        # Bottom < 0.
        {'left': 1, 'right': 15, 'top': 15, 'bottom': -1},
        # Top > height..
        {'left': 1, 'right': 15, 'top': 600, 'bottom': 0},
        # Width < 10.
        {'left': 1, 'right': 5, 'top': 15, 'bottom': 1},
        {'left': 1, 'right': 10, 'top': 15, 'bottom': 1},
        # Height < 10
        {'left': 1, 'right': 15, 'top': 5, 'bottom': 1},
        {'left': 1, 'right': 15, 'top': 10, 'bottom': 1},
    ]

    for bounds in bad_bounds_list:
      bid_response, record = self.CreateSuccessfulTemplateRecord()
      bid_response.ad[0].template_parameter[0].left = bounds['left']
      bid_response.ad[0].template_parameter[0].right = bounds['right']
      bid_response.ad[0].template_parameter[0].top = bounds['top']
      bid_response.ad[0].template_parameter[0].bottom = bounds['bottom']

      record.payload = bid_response.SerializeToString()
      self.records = [record]
      self.summarizer = log.LogSummarizer(self.records)
      self.summarizer.Summarize()
      self.CheckNProblematicResponses(1)
      self.assertTrue(record in self.summarizer._problematic)
      # For some cases we have a stacking error.
      self.assertTrue(len(record.problems) in [1, 2])

  def testSummarizeTemplateBadStacking(self):
    """Tests summarizing a template ad that doesn't stack correctly."""
    # A variety of invalid bounds, each item in the list is a 2 item list, one
    # for each ad.
    bad_bounds_list = [
        # Overlapping vertically.
        [{'left': 1, 'right': 15, 'top': 15, 'bottom': 0},
         {'left': 1, 'right': 15, 'top': 30, 'bottom': 14}],
        # Overlapping horizontally.
        [{'left': 1, 'right': 15, 'top': 15, 'bottom': 0},
         {'left': 14, 'right': 25, 'top': 15, 'bottom': 0}],
        # Overlapping both vertically and  horizontally.
        [{'left': 1, 'right': 15, 'top': 15, 'bottom': 0},
         {'left': 14, 'right': 25, 'top': 25, 'bottom': 10}],
    ]

    for bounds in bad_bounds_list:
      bid_response, record = self.CreateSuccessfulTemplateRecord()
      for i, ad_bounds in enumerate(bounds):
        bid_response.ad[0].template_parameter[i].left = ad_bounds['left']
        bid_response.ad[0].template_parameter[i].right = ad_bounds['right']
        bid_response.ad[0].template_parameter[i].top = ad_bounds['top']
        bid_response.ad[0].template_parameter[i].bottom = ad_bounds['bottom']

      record.payload = bid_response.SerializeToString()
      self.records = [record]
      self.summarizer = log.LogSummarizer(self.records)
      self.summarizer.Summarize()
      self.CheckNProblematicResponses(1)
      self.assertTrue(record in self.summarizer._problematic)
      # For some cases we have a stacking error.
      self.assertEqual(1, len(record.problems))

  def testSummarizeTemplateAdForVideoRequest(self):
    """Tests summarizing a template ad for a video ad request.."""
    bid_response, record = self.CreateSuccessfulTemplateRecord()
    record.bid_request.video.videoad_start_delay = 1000
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.CheckNProblematicResponses(1)
    self.assertTrue(record in self.summarizer._problematic)
    self.assertEqual(1, len(record.problems))

  def CheckLogHasNLines(self, log_obj, n, exact=False):
    """Checks that the given StringIO object contains n or more lines of text.

    Args:
      log_obj - A StringIO instance.
      n - The expected number of new lines to find.
      exact - Whether to check for exactly n lines or >= n lines.
    """
    if exact:
      self.assertTrue(log_obj.getvalue().count('\n') == n)
    else:
      self.assertTrue(log_obj.getvalue().count('\n') >= n)

  def testWriteLogsWhileEmpty(self):
    """Tests writing logs with empty record lists."""
    self.SetupLogs()
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.WriteLogFiles(self.good_log, self.problematic_log,
                                  self.invalid_log, self.error_log,
                                  self.snippet_log)
    self.CheckLogHasNLines(self.good_log, 0, exact=True)
    self.CheckLogHasNLines(self.problematic_log, 0, exact=True)
    self.CheckLogHasNLines(self.invalid_log, 0, exact=True)
    self.CheckLogHasNLines(self.error_log, 0, exact=True)

  def testWriteLogsWithGoodReponse(self):
    """Tests writing logs with one good response."""
    self.SetupLogs()
    _, record = self.CreateSuccessfulRecord()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.summarizer.WriteLogFiles(self.good_log, self.problematic_log,
                                  self.invalid_log, self.error_log,
                                  self.snippet_log)
    self.CheckLogHasNLines(self.problematic_log, 0, exact=True)
    self.CheckLogHasNLines(self.invalid_log, 0, exact=True)
    self.CheckLogHasNLines(self.error_log, 0, exact=True)
    self.CheckLogHasNLines(self.good_log, 3)
    self.assertEqual(1, self.snippet_log.getvalue().count('<li>'))

  def testWriteLogsWithMultipleGoodResponses(self):
    """Tests writing logs with two good responses."""
    self.SetupLogs()
    _, record = self.CreateSuccessfulRecord()
    self.records.append(record)
    _, record = self.CreateSuccessfulRecord()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.summarizer.WriteLogFiles(self.good_log, self.problematic_log,
                                  self.invalid_log, self.error_log,
                                  self.snippet_log)
    self.CheckLogHasNLines(self.problematic_log, 0, exact=True)
    self.CheckLogHasNLines(self.invalid_log, 0, exact=True)
    self.CheckLogHasNLines(self.error_log, 0, exact=True)
    self.CheckLogHasNLines(self.good_log, 5)
    self.assertEqual(2, self.snippet_log.getvalue().count('<li>'))

  def testWriteLogsWithInvalidReponse(self):
    """Tests writing logs with one invalid response."""
    self.SetupLogs()
    _, record = self.CreateSuccessfulRecord()
    record.payload = 'garbage'
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.summarizer.WriteLogFiles(self.good_log, self.problematic_log,
                                  self.invalid_log, self.error_log,
                                  self.snippet_log)
    self.CheckLogHasNLines(self.good_log, 0, exact=True)
    self.CheckLogHasNLines(self.problematic_log, 0, exact=True)
    self.CheckLogHasNLines(self.invalid_log, 3)
    self.CheckLogHasNLines(self.error_log, 0, exact=True)
    self.assertEqual(0, self.snippet_log.getvalue().count('<li>'))

  def testWriteLogsWithErrorReponse(self):
    """Tests writing logs with one error response."""
    self.SetupLogs()
    _, record = self.CreateSuccessfulRecord()
    record.status = 400
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.summarizer.WriteLogFiles(self.good_log, self.problematic_log,
                                  self.invalid_log, self.error_log,
                                  self.snippet_log)
    self.CheckLogHasNLines(self.good_log, 0, exact=True)
    self.CheckLogHasNLines(self.problematic_log, 0, exact=True)
    self.CheckLogHasNLines(self.invalid_log, 0, exact=True)
    self.CheckLogHasNLines(self.error_log, 3)
    self.assertEqual(0, self.snippet_log.getvalue().count('<li>'))

  def testWriteLogsWithProblematicReponse(self):
    """Tests writing logs with one problematic response."""
    self.SetupLogs()
    bid_response, record = self.CreateSuccessfulRecord()
    bid_response.ad[0].ClearField('click_through_url')
    record.payload = bid_response.SerializeToString()
    self.records.append(record)
    self.summarizer = log.LogSummarizer(self.records)
    self.summarizer.Summarize()
    self.summarizer.WriteLogFiles(self.good_log, self.problematic_log,
                                  self.invalid_log, self.error_log,
                                  self.snippet_log)
    self.CheckLogHasNLines(self.good_log, 0, exact=True)
    self.CheckLogHasNLines(self.problematic_log, 3)
    self.CheckLogHasNLines(self.invalid_log, 0, exact=True)
    self.CheckLogHasNLines(self.error_log, 0, exact=True)
    self.assertEqual(1, self.snippet_log.getvalue().count('<li>'))


class TestFunctions(unittest.TestCase):
  """Tests functions in the log module."""

  def testEscapeUrl(self):
    """Tests escaping a string."""
    # For documentation about how the string is escaped see:
    # https://sites.google.com/a/google.com/adx-rtb/technical-documentation/response
    alphanum = 'abcdefghijklmnopqrstxyzuvwABCDEFGHIJKLMNOPQRSTXYZUVW0123456789'
    unchanged = '!()*,-./:_~'
    escapable = '<>=;'
    escaped = "".join(['%%%X' % ord(c) for c in escapable])
    unescaped = alphanum + unchanged + escapable
    result = log.EscapeUrl(unescaped)
    self.assertEqual(alphanum + unchanged + escaped, result)


if __name__ == '__main__':
  unittest.main()
