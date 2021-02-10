
# NIRSPEC fiber injection unit. Build tracking camera

override SYSNAM = kss/nirspec/nsfiu/processing/
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELLIB = Track_Cam_process.py
LIBSUB = python

# include sub directories
DIRS = TC_Base TC_Vis

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