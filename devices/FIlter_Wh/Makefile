# NIRSPEC fiber extraction unit. Build pyramid wavefront sensor pickoff

override SYSNAM = kss/nirspec/nsfiu/devices/Filter_Wh
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELLIB = Filter_Wh_cmds.py
RELBIN = Filter_Wh_Control Filter_Wh_draw Filter_Wh
RELDAT = Filter_Wh.ini
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
