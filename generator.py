#!/usr/bin/python
# Copyright 2009 Google Inc. All Rights Reserved.
"""A class to generate random BidRequest protocol buffers."""

import base64
import random
import time

import realtime_bidding_pb2

PROTOCOL_VERSION = 1

BID_REQUEST_ID_LENGTH = 16  # In bytes.
COOKIE_LENGTH = 20  # In bytes.
COOKIE_VERSION = 1

# Placement.
CHANNELS = ['12345']

# Data describing branded publishers.
# Tuple description: (publisher url, seller id, publisher settings id, seller)
# The below are example values for these fields that are used to populate
# publisher info.
BRANDED_PUB_DATA = [
    ('http://www.youtube.com', 502, 32423234, 'Youtube'),
    ('http://www.youtube.com/shows', 502, 32423234, 'Youtube'),
    ('http://news.google.com', 10001, 56751341, 'Google News'),
    ('http://news.google.com/news?pz=1&ned=us&topic=b&ict=ln', 10001, 12672383,
     'Google News'),
    ('http://www.google.com/finance?hl=en&ned=us&tab=ne', 1528, 84485234,
     'Google Finance'),
    ('http://www.nytimes.com/pages/technology/index.html', 936, 9034124,
     'New York Times'),
    ('http://some.gcn.site.com', 10002, 12002392, 'GCN'),
]

# Data for anonymous publishers.
# Tuple description: (anonymous url, publisher settings id)
ANONYMOUS_PUB_DATA = [
    ('http://1.google.anonymous/', 90002301),
    ('http://2.google.anonymous/', 90002302),
    ('http://3.google.anonymous/', 90002303),
    ('http://4.google.anonymous/', 93002304),
    ('http://5.google.anonymous/', 93002305),
]

MAX_ADGROUP_ID = 99999999
MAX_DIRECT_DEAL_ID = 1 << 62
MAX_MATCHING_ADGROUPS = 3

DIMENSIONS = [
    (468, 60),
    (120, 600),
    (728, 90),
    (300, 250),
    (250, 250),
    (336, 280),
    (120, 240),
    (125, 125),
    (160, 600),
    (180, 150),
    (110, 32),
    (120, 60),
    (180, 60),
    (420, 600),
    (420, 200),
    (234, 60),
    (200, 200),
]

MAX_SLOT_ID = 200

# Verticals.
MAX_NUM_VERTICALS = 5
VERTICALS = [
    66, 563, 607, 379, 380, 119, 570, 22, 355, 608, 540, 565, 474, 433, 609,
    23, 24,
]

# Geo.
LANGUAGE_CODES = ['en']

# Example geo targets used to populate requests.
# Tuple description (geo_criteria_id, postal code, postal code prefix)
# Only one of postal code or postal code prefix will be set.
# Canada has only postal code prefixes available.
GEO_CRITERIA = [
    (9005559, '10116', None),  # New York, United States
    (9031936, '94087', None),  # California, United States
    (1015214, '33601', None),  # Tampa, Florida, United States
    (1021337, '27583', None),  # Timberlake, North Carolina, United States
    (1012873, '99501', None),  # Anchorage, Alaska, United States
    (1018127, '02102', None),  # Boston, Massachusetts, United States
    (1002451, None, 'M4C'),  # Toronto, Ontario, Canada
    (1002113, None, 'B3H'),  # Halifax, Nova Scotia, Canada
    (1002061, None, 'E1B'),  # Moncton, New Brunswick, Canada
    (1000278, '2753', None),  # Richmond, New South Wales, Australia
    (1000142, '2600', None),  # Canberra, Australian Capital Territory,Australia
    (1000414, '4810', None),  # Townsville, Queensland, Australia
    (1000567, '3000', None),  # Melbourne, Victoria, Australia
]

# User info.
USER_AGENTS = [
    'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.0.2) '
    'Gecko/2008092313 Ubuntu/8.04 (hardy) Firefox/3.1',
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.8.1.2pre) '
    'Gecko/20070118 Firefox/2.0.0.2pre',
    'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.1.7pre) Gecko/20070815 '
    'Firefox/2.0.0.6 Navigator/9.0b3',
    'Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10_4_11; en) AppleWebKit/528.5+'
    ' (KHTML, like Gecko) Version/4.0 Safari/528.1',
    'Mozilla/5.0 (Macintosh; U; PPC Mac OS X; sv-se) AppleWebKit/419 '
    '(KHTML, like Gecko) Safari/419.3',
    'Mozilla/5.0 (Windows; U; MSIE 7.0; Windows NT 6.0; en-US)',
    'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0;)',
    'Mozilla/4.08 (compatible; MSIE 6.0; Windows NT 5.1)',
]

# Criteria.
MAX_EXCLUDED_ATTRIBUTES = 3
CREATIVE_ATTRIBUTES = [1, 2, 3, 4, 5, 6, 7, 8, 9]

MAX_EXCLUDED_BUYER_NETWORKS = 2

MAX_INCLUDED_VENDOR_TYPES = 10
VENDOR_TYPES = [
    0, 10, 28, 42, 51, 65, 71, 92, 94, 113, 126, 128, 129, 130, 143, 144, 145,
    146, 147, 148, 149, 152, 179, 194, 198, 225, 226, 227, 228, 229, 230, 231,
    232, 233, 234, 235, 236, 237, 238, 255, 303,  311, 312, 313, 314, 315, 316,
]
INSTREAM_VIDEO_VENDOR_TYPES = [297, 220, 306, 307, 308, 309, 310, 317, 318,]

MAX_EXCLUDED_CATEGORIES = 4
AD_CATEGORIES = [0, 3, 4, 5, 7, 8, 10, 18, 19, 23, 24, 25,]


MAX_TARGETABLE_CHANNELS = 3
TARGETABLE_CHANNELS = [
    'all top banner ads', 'right hand side banner', 'sports section',
    'user generated comments', 'weather and news',
]

# Mobile constants.
DEFAULT_MOBILE_PROPORTION = 0.2
# Identifiers for mobile carriers that devices use to connect to the internet.
# See https://developers.google.com/adwords/api/docs/appendix/mobilecarriers
MOBILE_CARRIERS = [70152, 70361, 70392, 71352]
# Device type constants.
PHONE = realtime_bidding_pb2.BidRequest.Mobile.HIGHEND_PHONE
TABLET = realtime_bidding_pb2.BidRequest.Mobile.TABLET
# Screen Orientation Constants.
PORTRAIT = realtime_bidding_pb2.BidRequest.Mobile.SCREEN_ORIENTATION_PORTRAIT
LANDSCAPE = realtime_bidding_pb2.BidRequest.Mobile.SCREEN_ORIENTATION_LANDSCAPE
# These category ids represent Google play store and iTunes app store ids that
# the mobile app belongs to. Its not set for mobile web requests. See
# https://developers.google.com/adwords/api/docs/appendix/mobileappcategories
MOBILE_ANDROID_CATEGORY_IDS = [60005, 60025, 60032, 60004, 60002]
MOBILE_IOS_CATEGORY_IDS = [60535, 60508, 60548, 60556, 60564]
NUM_CATEGORIES = len(MOBILE_ANDROID_CATEGORY_IDS)
assert NUM_CATEGORIES == len(MOBILE_IOS_CATEGORY_IDS)
# Mobile device specific field collection where each row describes a device.
# Tuple description (platform, os major version, os minor version, os micro
# version, device type, is_app, is_interstitial, screen orientation, ad slot
# width, ad slot height, user agent)
# is_app: flag that indicates requests from app when set, mobile web requests
# when unset.
# is_interstitial: indicates interstitial app requests.
MOBILE_DEVICE_INFO = [
    ('iphone', 6, 1, 2, PHONE, True, False, PORTRAIT, 320, 50,
     'Mozilla/5.0 (iPhone; CPU iPhone OS 6_1_2 like Mac OS X) AppleWebKit/'
     '536.26 (KHTML, like Gecko) Mobile/10B146,gzip(gfe)'),
    ('android', 2, 3, 6, PHONE, True, False, LANDSCAPE, 320, 50,
     'Mozilla/5.0 (Linux; U; Android 2.3.6; it-it; GT-S5570I Build/GINGERBREAD)'
     ' AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1 '
     '(Mobile; afma-sdk-a-v6.1.0),gzip(gfe)'),
    ('android', 4, 1, 1, TABLET, True, False, LANDSCAPE, 728, 90,
     'Mozilla/5.0 (Linux; U; Android 4.1.1; fr-ca; GT-P3113 Build/JRO03C) '
     'AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30 (Mobile;'
     ' afma-sdk-a-v6.1.0),gzip(gfe)'),
    ('ipad', 6, 1, 2, TABLET, True, True, LANDSCAPE, 768, 1024,
     'Mozilla/5.0 (iPad; CPU OS 6_1_2 like Mac OS X) AppleWebKit/536.26'
     ' (KHTML, like Gecko) Mobile/10B146,gzip(gfe)'),
    ('android', 4, 0, 4, PHONE, True, True, PORTRAIT, 360, 640,
     'Mozilla/5.0 (Linux; U; Android 4.0.4; en-us; DROID BIONIC '
     'Build/6.7.2-223_DBN_M4-23) AppleWebKit/534.30 (KHTML, like Gecko) '
     'Version/4.0 Mobile Safari/534.30 (Mobile; afma-sdk-a-v6.2.1),gzip(gfe)'),
    ('ipad', 5, 1, 1, TABLET, True, False, PORTRAIT, 468, 60,
     'Mozilla/5.0 (iPad; CPU OS 5_1_1 like Mac OS X) AppleWebKit/534.46 (KHTML,'
     'like Gecko) Mobile/9B206,gzip(gfe)'),
    ('android', 2, 3, 5, PHONE, False, False, 0, 728, 90,
     'Mozilla/5.0 (Linux; U; Android 2.3.5; en-us; DROID X2 Build/'
     '4.5.1A-DTN-200-18) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 '
     'Mobile Safari/533.1,gzip(gfe)'),
    ('iphone', 4, 2, 1, PHONE, False, False, 0, 728, 90,
     'Mozilla/5.0 (iPod; U; CPU iPhone OS 4_2_1 like Mac OS X; en-us) '
     'AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8C148 '
     'Safari/6533.18.5,gzip(gfe)'),
    ('blackberry', 9, 2, 20, PHONE, False, False, 0, 320, 50,
     'Mozilla/5.0 (BlackBerry; U; BlackBerry 9220; en) AppleWebKit/534.11+ '
     '(KHTML, like Gecko) Version/7.1.0.337 Mobile Safari/534.11+,gzip(gfe)')
]
NUM_MOBILE_DEVICES = len(MOBILE_DEVICE_INFO)
ANDROID_APP_IDS = ['com.foo.bar', 'fus.ro.dah', 'test.app.id', 'a.b.c',
                   'com.one.two']
IOS_APP_IDS = ['610434022', '4453712097', '530434022', '445275396', '610424031']
MOBILE_VENDOR_TYPES = [423, 534]

MAX_INCLUDED_VENDOR_TYPES = 10

DEFAULT_INSTREAM_VIDEO_PROPORTION = 0.1
INSTREAM_VIDEO_START_DELAY_MAX_SECONDS = 60
INSTREAM_VIDEO_DURATION_MAX_SECONDS = 60
# Types of invideo_requests.
INSTREAM_VIDEO_PREROLL = 0
INSTREAM_VIDEO_MIDROLL = 1
INSTREAM_VIDEO_POSTROLL = -1
INSTREAM_VIDEO_TYPES = [
    INSTREAM_VIDEO_PREROLL, INSTREAM_VIDEO_MIDROLL, INSTREAM_VIDEO_POSTROLL]

random.seed(time.time())


class RandomBidGeneratorWrapper(object):
  """Generates random BidRequests."""

  def __init__(self, google_id_list=None,
               instream_video_proportion=DEFAULT_INSTREAM_VIDEO_PROPORTION,
               mobile_proportion=DEFAULT_MOBILE_PROPORTION,
               adgroup_ids_list=None):
    """Constructs a new RandomBidGenerator.

    Args:
      google_id_list: A list of Google IDs (as strings), or None to randomly
          generate IDs.
      instream_video_proportion: The proportion of requests which are for
          instream video ads [0.0, 1.0].
      mobile_proportion: Fraction of requests that are from a mobile device.
      adgroup_ids_list: A list of AdGroup IDs (as ints), or None to randomly
          generate IDs.
    """
    self._instream_video_proportion = instream_video_proportion
    self._mobile_proportion = mobile_proportion
    self._default_bid_generator = DefaultBidGenerator(google_id_list,
                                                      adgroup_ids_list)
    self._mobile_bid_generator = MobileBidGenerator(google_id_list,
                                                    adgroup_ids_list)
    self._video_bid_generator = VideoBidGenerator(google_id_list,
                                                  adgroup_ids_list)

  def GenerateBidRequest(self):
    """Generates a random BidRequest.

    Returns:
      An instance of realtime_bidding_pb2.BidRequest.
    """
    random_number = random.random()
    if random_number < self._instream_video_proportion:
      return self._video_bid_generator.GenerateBidRequest()
    elif random_number < (self._instream_video_proportion
                          + self._mobile_proportion):
      return self._mobile_bid_generator.GenerateBidRequest()
    # else
    return self._default_bid_generator.GenerateBidRequest()

  def GeneratePingRequest(self):
    """Generates a special ping request.

    Returns:
      A ping request with a generated id.
    """
    return self._default_bid_generator.GeneratePingRequest()


class DefaultBidGenerator(object):
  """Base bid request generator."""

  def __init__(self, google_id_list=None, adgroup_ids_list=None):
    """Constructor for the base generator.

    Args:
      google_id_list: A list of Google IDs (as strings), or None to randomly
          generate IDs.
      adgroup_ids_list: A list of AdGroup IDs (as ints), or None to randomly
          generate IDs.
    """
    self._google_id_list = google_id_list
    if adgroup_ids_list is not None:
      self._adgroup_ids = set(adgroup_ids_list)
    else:
      self._adgroup_ids = None
    self._vendor_types = VENDOR_TYPES
    self._slot_width, self._slot_height = random.choice(DIMENSIONS)
    self._user_agent_list = USER_AGENTS

  def GenerateBidRequest(self):
    """Generates a random BidRequest.

    Returns:
      An instance of realtime_bidding_pb2.BidRequest.
    """
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.is_test = True
    bid_request.id = self._GenerateId(BID_REQUEST_ID_LENGTH)
    bid_request.user_agent = random.choice(USER_AGENTS)
    self._GeneratePageInfo(bid_request)
    self._GenerateUserInfo(bid_request)
    self._GenerateAdSlot(bid_request)

    return bid_request

  def GeneratePingRequest(self):
    """Generates a special ping request.

    A ping request only has the id and is_ping fields set.

    Returns:
      An instance of realtime_bidding_pb2.BidRequest.
    """
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.id = self._GenerateId(BID_REQUEST_ID_LENGTH)
    bid_request.is_ping = True
    return bid_request

  def _GenerateId(self, length):
    """Generates a random ID.

    The generated ID is not guaranteed to be unique.

    Args:
      length: Length of generated ID in bytes.
    Returns:
      A random ID of the given length.
    """
    random_id = ''
    for _ in range(length):
      random_id += chr(random.randint(0, 255))
    return random_id

  def _GeneratePublisherData(self, bid_request):
    """Generates publisher fields.

    A random decision is made to choose between anonymous and branded data.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance
    """
    # 50% chance of anonymous ID/branded URL.
    if random.choice([True, False]):
      url, seller_id, pub_id, seller = random.choice(BRANDED_PUB_DATA)
      bid_request.url = url
      bid_request.seller_network_id = seller_id
      bid_request.publisher_settings_list_id = pub_id
      bid_request.DEPRECATED_seller_network = seller
    else:
      anonymous_id, pub_id = random.choice(ANONYMOUS_PUB_DATA)
      bid_request.anonymous_id = anonymous_id
      bid_request.publisher_settings_list_id = pub_id

  def _GeneratePageInfo(self, bid_request):
    """Generates page information for the given bid_request.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance
    """
    self._GeneratePublisherData(bid_request)
    bid_request.detected_language = random.choice(LANGUAGE_CODES)
    self._GenerateVerticals(bid_request)

  def _GenerateAdSlot(self, bid_request):
    """Generates a single ad slot with random data.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance
    """
    ad_slot = bid_request.adslot.add()
    ad_slot.id = random.randint(1, MAX_SLOT_ID)
    if self._slot_width is not None:
      ad_slot.width.append(self._slot_width)
    if self._slot_height is not None:
      ad_slot.height.append(self._slot_height)

    num_included_vendor_types = random.randint(1, MAX_INCLUDED_VENDOR_TYPES)
    for allowed_vendor in self._GenerateSet(self._vendor_types,
                                            num_included_vendor_types):
      ad_slot.allowed_vendor_type.append(allowed_vendor)

    # Generate random excluded creative attributes.
    num_excluded_creative_attributes = random.randint(1,
                                                      MAX_EXCLUDED_ATTRIBUTES)
    for creative_attribute in self._GenerateSet(
        CREATIVE_ATTRIBUTES, num_excluded_creative_attributes):
      ad_slot.excluded_attribute.append(creative_attribute)

    # Generate excluded categories for 20% of requests.
    if random.random() < 0.2:
      num_excluded_categories = random.randint(1, MAX_EXCLUDED_CATEGORIES)
      for excluded_category in self._GenerateSet(AD_CATEGORIES,
                                                 num_excluded_categories):
        ad_slot.excluded_sensitive_category.append(excluded_category)

    # Generate ad slot publisher settings list id by combining bid request
    # pub settings id and slot id.
    ad_slot.publisher_settings_list_id = (bid_request.publisher_settings_list_id
                                          + ad_slot.id)

    # We generate channels only for branded sites, simplifying by using the
    # same list of channels for all publishers.
    if bid_request.HasField('seller_network_id'):
      # Send only for 10% of bid requests, to simulate that few bid requests
      # have targetable channels in reality.
      send_channels = random.random < 0.1
      if send_channels:
        num_targetable_channels = random.randint(1, MAX_TARGETABLE_CHANNELS)
        for channel in self._GenerateSet(TARGETABLE_CHANNELS,
                                         num_targetable_channels):
          ad_slot.targetable_channel.append(channel)

    # Generate adgroup IDs, either randomly or from the ID list parameter
    if self._adgroup_ids:
      num_matching_adgroups = random.randint(1, len(self._adgroup_ids))
      generated_ids = random.sample(self._adgroup_ids, num_matching_adgroups)
    else:
      num_matching_adgroups = random.randint(1, MAX_MATCHING_ADGROUPS)
      generated_ids = [random.randint(1, MAX_ADGROUP_ID)
                       for _ in xrange(num_matching_adgroups)]

    for generated_id in generated_ids:
      ad_data = ad_slot.matching_ad_data.add()
      ad_data.adgroup_id = generated_id

      # 10% of adgroup requests will have a direct deal enabled
      if random.random() < 0.10:
        direct_deal = ad_data.direct_deal.add()
        direct_deal.direct_deal_id = random.randint(1, MAX_DIRECT_DEAL_ID)
        direct_deal.fixed_cpm_micros = random.randint(1, 99) * 10000
        ad_data.minimum_cpm_micros = direct_deal.fixed_cpm_micros

  def _GenerateVerticals(self, bid_request):
    """Populates bid_request with random verticals.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance.
    """
    verticals = self._GenerateSet(VERTICALS, MAX_NUM_VERTICALS)
    for vertical in verticals:
      vertical_pb = bid_request.detected_vertical.add()
      vertical_pb.id = vertical
      vertical_pb.weight = random.random()

  def _GenerateGoogleID(self, bid_request):
    """Generates the google id field.

    If the RandomBidGenerator was initated with a list of Google IDs, one of
    these is picked at random, otherwise a random ID is generated.

    Args:
      bid_request: A realtime_bidding_pb2.BidRequest instance.
    """
    if self._google_id_list:
      bid_request.google_user_id = random.choice(self._google_id_list)
    else:
      hashed_cookie = self._GenerateId(COOKIE_LENGTH)
      google_user_id = base64.urlsafe_b64encode(hashed_cookie)
      # Remove padding, i.e. remove '='s off the end.
      bid_request.google_user_id = google_user_id[:google_user_id.find('=')]
    # Cookie age of [1 second, 30 days).
    bid_request.cookie_age_seconds = random.randint(1, 60*60*24*30)

  def _GenerateUserInfo(self, bid_request):
    """Generates random user information.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance
    """
    geo_id, postal, postal_prefix = random.choice(GEO_CRITERIA)
    bid_request.geo_criteria_id = geo_id
    if postal:
      bid_request.postal_code = postal
    elif postal_prefix:
      bid_request.postal_code_prefix = postal_prefix
    self._GenerateGoogleID(bid_request)
    bid_request.cookie_version = COOKIE_VERSION
    # 4 bytes in IPv4, but last byte is truncated giving an overall length of 3
    # bytes.
    ip = self._GenerateId(3)
    bid_request.ip = ip

  def _GenerateSet(self, collection, set_size):
    """Generates a set of randomly chosen elements from the given collection.

    Args:
      collection: a list-like collection of elements
      set_size: the size of set to generate

    Returns:
      A set of randomly chosen elements from the given collection.
    """
    unique_collection = set(collection)
    if len(unique_collection) < set_size:
      return unique_collection

    s = set()
    while len(s) < set_size:
      s.add(random.choice(collection))

    return s


class VideoBidGenerator(DefaultBidGenerator):
  """Video bid request generator."""

  def __init__(self, google_id_list=None, adgroup_ids_list=None):
    """Constructor for the video request generator.

    Args:
      google_id_list: A list of Google IDs (as strings), or None to randomly
          generate IDs.
      adgroup_ids_list: A list of AdGroup IDs (as ints), or None to randomly
          generate IDs.
    """
    DefaultBidGenerator.__init__(self, google_id_list, adgroup_ids_list)
    self._slot_width = None
    self._slot_height = None
    self._vendor_types = INSTREAM_VIDEO_VENDOR_TYPES

  def _GeneratePageInfo(self, bid_request):
    """Generates page information for the given video bid request.

    Args:
      bid_request: a realtime_bidding_pb2.BidRequest instance
    """
    # Call the base class page info generate method.
    super(VideoBidGenerator, self)._GeneratePageInfo(bid_request)
    # Add video specific fields.
    video = bid_request.video
    request_type = random.choice(INSTREAM_VIDEO_TYPES)

    if request_type == INSTREAM_VIDEO_MIDROLL:
      delay_seconds = random.randint(1,
                                     INSTREAM_VIDEO_START_DELAY_MAX_SECONDS)
      video.videoad_start_delay = delay_seconds * 1000  # In milliseconds.
    else:
      video.videoad_start_delay = request_type

    # 50% chance of setting max_ad_duration.
    if random.choice([True, False]):
      max_ad_duration_seconds = random.randint(
          1, INSTREAM_VIDEO_DURATION_MAX_SECONDS)
      # In milliseconds.
      video.max_ad_duration = max_ad_duration_seconds * 1000


class MobileBidGenerator(DefaultBidGenerator):
  """Mobile bid request generator."""

  def __init__(self, google_id_list=None, adgroup_ids_list=None):
    """Constructor for the mobile request generator.

    Args:
      google_id_list: A list of Google IDs (as strings), or None to randomly
          generate IDs.
      adgroup_ids_list: A list of AdGroup IDs (as ints), or None to randomly
          generate IDs.
    """
    DefaultBidGenerator.__init__(self, google_id_list, adgroup_ids_list)
    self._slot_width = None
    self._slot_height = None
    self._vendor_types = MOBILE_VENDOR_TYPES

  def GenerateBidRequest(self):
    """Generates a random BidRequest.

    Randomly picks device info from available set, sets user agent and screen
    sizes before calling parent generate bid request.
    Returns:
      An instance of realtime_bidding_pb2.BidRequest.
    """
    bid_request = realtime_bidding_pb2.BidRequest()
    bid_request.is_test = True
    bid_request.id = self._GenerateId(BID_REQUEST_ID_LENGTH)
    self._GeneratePageInfo(bid_request)
    # Pick a mobile device at random.
    (platform, os_major_version, os_minor_version, os_micro_version,
     device_type, is_app_request, is_interstitial, orientation,
     self._slot_width, self._slot_height,
     bid_request.user_agent) = random.choice(MOBILE_DEVICE_INFO)

    # Add mobile fields
    mobile = bid_request.mobile
    mobile.carrier_id = random.choice(MOBILE_CARRIERS)
    mobile.platform = platform
    mobile.os_version.os_version_major = os_major_version
    mobile.os_version.os_version_minor = os_minor_version
    mobile.os_version.os_version_micro = os_micro_version
    mobile.mobile_device_type = device_type
    mobile.is_app = is_app_request
    mobile.is_interstitial_request = is_interstitial
    mobile.screen_orientation = orientation
    if is_app_request:
      category_ids = None
      if platform == 'android':
        category_ids = self._GenerateSet(MOBILE_ANDROID_CATEGORY_IDS,
                                         random.randint(1, NUM_CATEGORIES))
        mobile.app_id = random.choice(ANDROID_APP_IDS)
      else:
        category_ids = self._GenerateSet(MOBILE_IOS_CATEGORY_IDS,
                                         random.randint(1, NUM_CATEGORIES))
        mobile.app_id = random.choice(IOS_APP_IDS)
      for category_id in category_ids:
        mobile.app_category_ids.append(category_id)

    self._GenerateUserInfo(bid_request)
    self._GenerateAdSlot(bid_request)

    return bid_request
