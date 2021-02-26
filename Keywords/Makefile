# KTL dispatcher and client libraries for the NIRSPEC "more" service (nsmores).
# This is a catch-all service that provides pure software keywords to fill in
# the gaps not covered by other, more hardware-focused services in NIRSPEC.


include ./Mk.service
#include ../Mk.instrument
override SYSNAM = kss/$(INSTRUMENT)/$(KTLSERVICE)
override VERNUM = 1.1


SUBST_STRICT = True

DIRS = xml config dispatcher


################################################################################
# KROOT boilerplate:
# Include general make rules, using default values for the key environment
# variables if they are not already set.

ifndef KROOT
	KROOT = /kroot
endif

ifndef RELNAM
	RELNAM = default
endif

ifndef RELDIR
	RELDIR = $(KROOT)/rel/$(RELNAM)
endif

include $(KROOT)/etc/config.mk
################################################################################
