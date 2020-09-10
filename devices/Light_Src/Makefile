# NIRSPEC fiber extraction unit. Build NSFIU light source translator

override SYSNAM = kss/nirspec/nsfiu/devices/Light_Src
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

RELLIB = Light_Src_cmds.py
RELBIN = Light_Src_Control Light_Src_draw Light_Src
RELDAT = Light_Src.ini
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
