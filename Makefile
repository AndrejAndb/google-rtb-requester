PROTO_COMPILER=/usr/bin/protoc
SRC_DIR = .
PROTO_SRC_DIR = .
DEST_DIR = .

all: realtime-bidding_pb2.py

realtime-bidding_pb2.py: realtime-bidding.proto
	$(PROTO_COMPILER) -I=$(SRC_DIR) --python_out=$(DEST_DIR) realtime-bidding.proto

test: realtime-bidding_pb2.py
	python generator_test.py
	python requester_test.py
	python sender_test.py
