
# NIRSPEC fiber extraction unit. Build TCP module

override SYSNAM = kss/nirspec/nsfiu/devices/TCP
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELLIB = TCP_cmds.py
RELBIN = TCP_Control TCP_draw
RELDAT = TCP.ini
LIBSUB = python


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

include $(RELDIR)/etc/defs.mk
################################################################################

ifneq "$(PYTHON3)" ""
	ENABLE_PYTHON3 = True
endif

################################################################################
include $(RELDIR)/etc/rules.mk
################################################################################
