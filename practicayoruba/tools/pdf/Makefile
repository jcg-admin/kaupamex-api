# Makefile — PracticaYoruba PDF helper (UC-PAY-10, ADR-017).
#
# Builds the libharu-based receipt generator. Requires libhpdf-dev (build) and
# libhpdf-2.3.0 (runtime). On Ubuntu 24.04:
#
#     sudo apt-get install -y libhpdf-dev
#     make            # produces ./pdf_receipt
#
# The server provisioner (e-comerce-server) must install libhpdf-dev and run
# `make` (or `make build`) in this directory during deploy so the binary exists
# next to the source. The Django view (apps/payments) invokes ./pdf_receipt via
# subprocess. See ADR-017 for the rationale (crash isolation from mod_wsgi).

CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra
LDLIBS  := -lhpdf
TARGET  := pdf_receipt
SRC     := pdf_receipt.c

.PHONY: all build clean check

all: build

build: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET) $(LDLIBS)

# Compile-only gate (ADR-017 gate 2): exits non-zero if it does not compile.
check:
	$(CC) $(CFLAGS) $(SRC) -o /tmp/pdf_receipt_check $(LDLIBS)
	@echo "pdf_receipt compiles OK"

clean:
	rm -f $(TARGET)
