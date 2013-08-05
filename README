A Python program to generate sample traffic for Real Time Bidders.

This program requires the Python Protocol Buffers library.  See
  http://code.google.com/p/protobuf/
for more details.

The included protocol buffer file is the latest at the time of publishing. If
you would like to use this application against another version of
realtime-bidding.proto, either copy the file into this directory or set the
PROTO_SRC_DIR variable in the Makefile to the directory containing
realtime-bidding.proto. Then execute:
make

You may need to change the Makefile if you are developing on Windows or if
the protocol compiler is at a location other than '/usr/bin/protoc'.

The requester script will attempt to send randomly generated BidRequest
protocol buffers to your Real Time Bidder at the specified URL using the HTTP
POST method.  These generated requests are similar to requests sent by the real
system.  The requester script will attempt to parse your responses.  It will
display a summary which includes the number of requests sent, number of
successful requests, and <response code, payload> of any responses that either
did not have the HTTP OK (200) response code or could not be parsed.

Before running this application you must generate the Python file for the
realtime-bidding.proto protocol buffer. You only need to do this once. Run the
command:
  make

In order to test your Real Time Bidder with a single request run the following
command, replacing <url> with the URL of your bidder:
  python requester.py  --url=<url> --max_qps=1 --requests=1

In order to test your Real Time Bidder with continuous requests use either
the --seconds or --requests option.  Use the --max_qps option to control the
load in queries per second.  For example:
  python requester.py  --url=<url> --max_qps=5 --requests=100
  python requester.py  --url=<url> --max_qps=1 --seconds=20
The requester script is not intended as a load-testing tool.

The requester tool will do macro substitutions on the HTML snippets you return
with the exception of the WINNING_PRICE macro. If you'd like a real encrypted
winning price you may use one of the sample encrypted prices provided by Google
together with the price decryption keys.  Here's an example:
./requester.py --requests=10 --url=<url> --max_qps=10 \
  --sample_encrypted_price=Sxl_ZQAHI5sKslcaIQYihiY0FOWqY8kmI2_esA
This will substitute the winning price macros with the given price for all ads.

In its normal mode of operation the requester tool will generate random Google
user ids (BidRequest.google_user_id field). If your bidder depends on specific
users to bid and you use the Cookie Matching service you can use the
--google_user_ids_file parameter. The value should be a path to a file with
Google user IDs (as returned by the Cookie Matching Service), one per line.
The requester tool will send randomly chosen user IDs from the provided list.

The requester tool will send requests for instream video ad requests, as well
as regular requests, you can set what proportion of the traffic is for instream
requests using the --instream_video_proportion flag (set to 0.1 by default).

The requester program will output some general statistics about the test as
well as some log files.  Empty log files are not generated.  The possible files
are:
 * good-<timestamp>.log
    Contains all successful bid requests and bid responses in human readable
    text format.
 * error-<timestamp>.log
    Contains all bid requests, HTTP response codes, and HTTP response payload
    for all responses that had a non-200 HTTP response code.
 * invalid-<timestamp>.log
    Contains all bid requests, and HTTP response payload for response payloads
    that could not be parsed into a BidResponse protocol buffer.
 * problematic-<timestamp>.log
    Contains all bid requests, bid responses, and problems for responses that
    could be parsed but for which problems were detected.
 * snippets-<timestamp>.html
    Contains all BidRequests, BidResponses and rendered HTML snippets for
    requests that had valid responses with valid snippets.  Note that
    the rendered snippets have an unencrypted winning price.

If not all requests were in the 'good' bucket, please check the appropriate
log file and fix any problems.
In addition please check the snippets*.html file to make sure that the ads
render as you expected.  Check that clicks work, make sure that the Google
click tracking URL gets a request during the chain of redirects using a tool
such as "Live HTTP Headers".  Please verify that the URL reached as a result
of a click is in the declared click-through URL list in the BidResponse.

We will ask you to send the output of the requester program as well as any log
files it produces and the snippets*.html file to Google before initiating a
handshake test from our systems.
