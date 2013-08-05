#!/usr/bin/python
# Copyright 2009 Google Inc. All Rights Reserved.
"""Unit tests for generator.py."""

import unittest

import generator
import realtime_bidding_pb2


class RandomBidGeneratorTest(unittest.TestCase):
  """Tests the RandomBidGenerator class."""

  def setUp(self):
    self.generator = generator.RandomBidGeneratorWrapper()
    self.default_generator = generator.DefaultBidGenerator()

  def testGeneratingOneRandomHtmlBidRequest(self):
    """Tests that generating one random html bid request works."""
    self.generator = generator.RandomBidGeneratorWrapper(
        instream_video_proportion=0.0, mobile_proportion=0.0)
    bid_request = self.generator.GenerateBidRequest()

    self.CheckCommonBidRequest(bid_request)

    # Html specific expectations.
    for adslot in bid_request.adslot:
      self.assertEqual(len(adslot.height), 1)
      self.assertEqual(len(adslot.width), 1)
      self.assertNotEqual(adslot.height[0], 0)
      self.assertNotEqual(adslot.width[0], 0)
      for vendor in adslot.allowed_vendor_type:
        self.assertTrue(vendor in generator.VENDOR_TYPES)

  def testGeneratingOneRandomVideoBidRequest(self):
    """Tests that generating one random instream video bid request works."""
    self.generator = generator.RandomBidGeneratorWrapper(
        instream_video_proportion=1.0, mobile_proportion=0.0)
    bid_request = self.generator.GenerateBidRequest()

    self.CheckCommonBidRequest(bid_request)

    # Instream video specific expectations.
    self.assertTrue(bid_request.HasField('video'))
    self.assertTrue(bid_request.video.HasField('videoad_start_delay'))
    # -1 = post roll, 0 = pre roll, positive number = mid roll.
    self.assertTrue(bid_request.video.videoad_start_delay >= -1)
    if bid_request.video.HasField('max_ad_duration'):
      # Duration must always be positive.
      self.assertTrue(bid_request.video.max_ad_duration > 0)

    for adslot in bid_request.adslot:
      self.assertEqual(len(adslot.height), 0)
      self.assertEqual(len(adslot.width), 0)
      for vendor in adslot.allowed_vendor_type:
        self.assertTrue(vendor in generator.INSTREAM_VIDEO_VENDOR_TYPES)

  def testGenerateOneMobileBidRequest(self):
    """Tests the generation of one mobile bid request."""
    self.generator = generator.RandomBidGeneratorWrapper(
        instream_video_proportion=0.0, mobile_proportion=1.0)
    bid_request = self.generator.GenerateBidRequest()

    self.CheckCommonBidRequest(bid_request)

    # Check for mobile specific fields.
    self.assertTrue(bid_request.HasField('mobile'))
    mobile = bid_request.mobile
    self.assertTrue(mobile.HasField('platform'))
    self.assertTrue(mobile.HasField('os_version'))
    self.assertTrue(mobile.HasField('mobile_device_type'))
    self.assertTrue(mobile.HasField('is_app'))
    self.assertTrue(mobile.HasField('is_interstitial_request'))
    self.assertTrue(mobile.HasField('screen_orientation'))
    for adslot in bid_request.adslot:
      # Check vendor type field.
      for vendor in adslot.allowed_vendor_type:
        self.assertTrue(vendor in generator.MOBILE_VENDOR_TYPES)
      # Check adslot width and height.
      self.assertTrue(len(adslot.width))
      self.assertTrue(len(adslot.height))
    # Check platform dependent app fields.
    if mobile.is_app:
      if mobile.platform == 'android':
        self.assertTrue(mobile.app_id in generator.ANDROID_APP_IDS)
        for app_category in mobile.app_category_ids:
          self.assertTrue(app_category in generator.MOBILE_ANDROID_CATEGORY_IDS)
      else:
        self.assertTrue(mobile.app_id in generator.IOS_APP_IDS)
        for app_category in mobile.app_category_ids:
          self.assertTrue(app_category in generator.MOBILE_IOS_CATEGORY_IDS)

  def CheckCommonBidRequest(self, bid_request):
    """Checks a bid request for expectations common among request types.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance
    """
    self.assertFalse(bid_request is None)
    self.assertTrue(bid_request.IsInitialized())
    self.assertTrue(
        (bid_request.HasField('url') and
         bid_request.HasField('seller_network_id'))
        or bid_request.HasField('anonymous_id'))

    expected_scalar_fields = [
        'is_test',
        'id',
        'detected_language',
        'geo_criteria_id',
        'google_user_id',
        'cookie_version',
        'cookie_age_seconds',
        'user_agent',
        'ip',
        'publisher_settings_list_id',
    ]
    for field in expected_scalar_fields:
      self.assertTrue(bid_request.HasField(field),
                      'Bid request missing field: %s' % field)

    # Either postal_code or postal_code_prefix should be defined
    if not bid_request.HasField('postal_code'):
      self.assertTrue(bid_request.HasField('postal_code_prefix') and
                      len(bid_request.postal_code_prefix) > 1,
                      'Bid request missing both postal_code and'
                      'postal_code_prefix')
    # Ip should be 3 bytes long (IPv4 with last byte truncated).
    self.assertEqual(3, len(bid_request.ip))

    self.assertTrue(len(bid_request.detected_vertical) > 0)
    for vertical in bid_request.detected_vertical:
      self.assertNotEqual(vertical.id, 0)
      self.assertNotEqual(vertical.id, 0)

    self.assertTrue(len(bid_request.adslot) > 0)
    for adslot in bid_request.adslot:
      self.assertEqual(len(adslot.DEPRECATED_allowed_attribute), 0)
      self.assertNotEqual(adslot.id, 0)
      self.assertTrue(len(adslot.excluded_attribute) > 0)
      self.assertTrue(len(adslot.allowed_vendor_type) > 0)
      self.assertTrue(len(adslot.matching_ad_data) > 0)
      self.assertNotEqual(adslot.publisher_settings_list_id, 0)
      if not bid_request.HasField('seller_network_id'):
        self.assertFalse(adslot.targetable_channel)
      for ad_data in adslot.matching_ad_data:
        self.assertTrue(ad_data.HasField('adgroup_id'))
        self.assertNotEqual(ad_data.adgroup_id, 0)

  def testGeneratePingRequest(self):
    """Tests generating a ping request."""
    bid_request = self.generator.GeneratePingRequest()
    self.assertFalse(bid_request is None)
    self.assertTrue(bid_request.IsInitialized())
    self.assertTrue(bid_request.HasField('is_ping'))
    self.assertTrue(bid_request.is_ping)

  def testGenerateGoogleIdFromList(self):
    """Tests generating a Google ID from a list."""
    # Real sample values from the Cookie Matching service.
    google_ids = [
        'CAESEBs2zXrUdzP08NfyRcwuOic',
        'CAESEGDp9dG8BR26gKybOFwKVnQ',
        'CAESELGsXo_3kPoHM2EdtzhqvSs',
        'CAESEPOq9BSD5GWBmb716V8R-uo',
        'CAESEJaOYa0vEUojtGMTlkf9UoM',
        'CAESECwK0aD3FY0QIaU6cA1ln2A',
    ]

    self.generator = generator.DefaultBidGenerator(google_ids)
    bid_request = realtime_bidding_pb2.BidRequest()
    self.generator._GenerateGoogleID(bid_request)
    self.assertTrue(bid_request.HasField('google_user_id'))
    self.assertTrue(bid_request.google_user_id in google_ids)

  def testGenerateRandomGoogleId(self):
    """Tests generating a random Google ID."""
    self.generator = generator.DefaultBidGenerator()
    bid_request = realtime_bidding_pb2.BidRequest()
    self.generator._GenerateGoogleID(bid_request)
    self.assertTrue(bid_request.HasField('google_user_id'))

  def testGenerateAdGroupIdsFromList(self):
    """Tests generating AdGroup IDs from a list."""
    adgroup_ids = [
        5642578842,
        5663180187,
        5663180325
    ]

    self.generator = generator.DefaultBidGenerator(adgroup_ids_list=adgroup_ids)
    bid_request = realtime_bidding_pb2.BidRequest()
    self.generator._GenerateAdSlot(bid_request)
    self.assertEqual(1, len(bid_request.adslot))
    adslot = bid_request.adslot[0]
    self.assertTrue(adslot.matching_ad_data)
    for matching_ad_data in adslot.matching_ad_data:
      self.assertTrue(matching_ad_data.adgroup_id in adgroup_ids,
                      '%s not in %s' % (matching_ad_data.adgroup_id,
                                        adgroup_ids))

  def testGeneratedBidRequestsNotEqual(self):
    """Tests that two generated bid requests are not equal."""
    bid_request1 = self.generator.GenerateBidRequest()
    bid_request2 = self.generator.GenerateBidRequest()
    self.assertNotEqual(bid_request1, bid_request2)

  def testGeneratedVideoBidRequestsNotEqual(self):
    """Tests that two generated video bid requests are not equal."""
    video_generator = generator.VideoBidGenerator()
    bid_request1 = video_generator.GenerateBidRequest()
    bid_request2 = video_generator.GenerateBidRequest()
    self.assertNotEqual(bid_request1, bid_request2)

  def testGeneratedMobileBidRequestsNotEqual(self):
    """Tests that two generated mobile bid requests are not equal."""
    mobile_generator = generator.MobileBidGenerator()
    bid_request1 = mobile_generator.GenerateBidRequest()
    bid_request2 = mobile_generator.GenerateBidRequest()
    self.assertNotEqual(bid_request1, bid_request2)

  def testGeneratedPublisherData(self):
    """Checks if populated publisher data is correct."""
    bid_request = self.generator.GenerateBidRequest()
    if bid_request.HasField('seller_network_id'):
      url = bid_request.url
      seller_id = bid_request.seller_network_id
      pub_id = bid_request.publisher_settings_list_id
      seller = bid_request.DEPRECATED_seller_network
      self.assertTrue((url, seller_id, pub_id, seller)
                      in generator.BRANDED_PUB_DATA)
    else:
      anonymous_id = bid_request.anonymous_id
      pub_id = bid_request.publisher_settings_list_id
      self.assertTrue((anonymous_id, pub_id)
                      in generator.ANONYMOUS_PUB_DATA)


if __name__ == '__main__':
  unittest.main()
