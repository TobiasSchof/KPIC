# KTLXML definition of the keywords associated with this service.
#

include ../Mk.service
override SYSNAM = kss/$(INSTRUMENT)/$(KTLSERVICE)/xml
override VERNUM = 1.1

SUBST_STRICT = True


KTLXML_FAMILY_SERVICE = $(KTLSERVICE)
KTLXML_DEPS = Makefile ../Mk.service

XML_SIN_IN  = $(wildcard *.xml.sin)
XML_SIN_OUT = $(XML_SIN_IN:%.sin=%)

RELDAT  = messages.xml keyword_ids.xml $(XML_SIN_OUT)
DATSUB  = $(KTLSERVICE)/xml

FILES = $(RELDAT)
PREFILES = $(FILES)
PREINSTALL = $(PREFILES)

DIRS = dtune ktldisp


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
