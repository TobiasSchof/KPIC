
# NIRSPEC fiber injection unit. Build tracking camera tracking processing

override SYSNAM = kss/nirspec/nsfiu/processing/TC_Track
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELBIN = Track_Cam_tracking_process_Control
RELDAT = Track_Cam_tracking_process.ini 

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