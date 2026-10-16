CC ?= cc
PYTHON ?= python3
WAYLAND_SCANNER ?= wayland-scanner
WAYLAND_CFLAGS ?= $(shell pkg-config --cflags wayland-client)
WAYLAND_LIBS ?= $(shell pkg-config --libs wayland-client)
NATIVE = .build/native
PROTOCOL = native/protocols/wlr-foreign-toplevel-management-unstable-v1.xml

.PHONY: test native test-c check
test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

$(NATIVE):
	mkdir -p $@

$(NATIVE)/foreign-toplevel-client-protocol.h: $(PROTOCOL) | $(NATIVE)
	$(WAYLAND_SCANNER) client-header $< $@

$(NATIVE)/foreign-toplevel-protocol.c: $(PROTOCOL) | $(NATIVE)
	$(WAYLAND_SCANNER) private-code $< $@

$(NATIVE)/own-toplevel: native/toplevel.c native/json_escape.h $(NATIVE)/foreign-toplevel-client-protocol.h $(NATIVE)/foreign-toplevel-protocol.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -std=c11 -Wall -Wextra -Werror -O2 $(WAYLAND_CFLAGS) -I$(NATIVE) native/toplevel.c $(NATIVE)/foreign-toplevel-protocol.c $(LDFLAGS) $(WAYLAND_LIBS) -o $@

native: $(NATIVE)/own-toplevel

test-c: | $(NATIVE)
	$(CC) -std=c11 -Wall -Wextra -Werror -g -fsanitize=address,undefined tests/test_json.c -o $(NATIVE)/test-json
	$(NATIVE)/test-json

check: test test-c
	$(PYTHON) scripts/check-source.py
