# NIRSPEC fiber injection unit. Build tip-tilt mirror

override SYSNAM = kss/nirspec/nsfiu/devices/Bundle
override VERNUM = 1.0

# If I knew that code would not work with Python 2 I would:
##override ENABLE_PYTHON2 = False
## DIRS = designer

RELLIB = Bundle.py
RELBIN = Bundle Bundle_Control Bundle_draw
RELDAT = Bundle.ini
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
