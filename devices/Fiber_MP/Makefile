# NIRSPEC fiber extraction unit. Build Fiber Multiport module

override SYSNAM = kss/nirspec/nsfiu/devices/Fiber_MP
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELLIB = Fiber_MP_cmds.py
RELBIN = Fiber_MP_Control Fiber_MP_draw
RELDAT = Fiber_MP.ini
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
