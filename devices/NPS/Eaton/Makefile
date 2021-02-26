# NIRSPEC fiber injection unit. Build Network Power Strip

override SYSNAM = kss/nirspec/nsfiu/devices/NPS/Eaton
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELLIB = NPS_cmds.py
RELDAT = NPS.ini
RELBIN = NPS NPS_Control
LIBSUB = python
##FILES = $(RELBIN)


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
