# Makefile — PracticaYoruba PDF helpers (UC-PAY-10, UC-RPT-04/UC-REP-05; ADR-017).
#
# Builds the libharu-based helpers:
#   pdf_receipt — purchase receipt (UC-PAY-10)
#   pdf_report  — report table export (UC-RPT-04 / UC-REP-05)
#
# Requires libhpdf-dev (build) and libhpdf-2.3.0 (runtime). On Ubuntu 24.04:
#
#     sudo apt-get install -y libhpdf-dev
#     make            # produces ./pdf_receipt and ./pdf_report
#
# The server provisioner (e-comerce-server) must install libhpdf-dev and run
# `make` (or `make build`) in this directory during deploy so BOTH binaries
# exist next to the source. The Django views invoke them via subprocess
# (apps/payments -> pdf_receipt, apps/reports -> pdf_report). See ADR-017 for
# the rationale (crash isolation from mod_wsgi).

CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra
LDLIBS  := -lhpdf
TARGETS := pdf_receipt pdf_report

.PHONY: all build clean check

all: build

build: $(TARGETS)

pdf_receipt: pdf_receipt.c
	$(CC) $(CFLAGS) pdf_receipt.c -o pdf_receipt $(LDLIBS)

pdf_report: pdf_report.c
	$(CC) $(CFLAGS) pdf_report.c -o pdf_report $(LDLIBS)

# Compile-only gate (ADR-017 gate 2): exits non-zero if either does not compile.
check:
	$(CC) $(CFLAGS) pdf_receipt.c -o /tmp/pdf_receipt_check $(LDLIBS)
	$(CC) $(CFLAGS) pdf_report.c -o /tmp/pdf_report_check $(LDLIBS)
	@echo "pdf_receipt + pdf_report compile OK"

clean:
	rm -f $(TARGETS)
