# NIRSPEC fiber injection unit. Build tracking camera

override SYSNAM = kss/nirspec/nsfiu/devices/Track_Cam
override VERNUM = 1.0

override ENABLE_PYTHON2 = False

SOURCE = Track_Cam_Control.cpp KPIC_Cam_Observer.cpp
RELINC = KPIC_Cam_Observer.hpp
RELBIN = Track_Cam_Control
RELDAT = Track_Cam.ini 
RELLIB = Track_Cam_cmds.py
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

# requires libpng12.x86_64
Track_Cam_Control: Track_Cam_Control.cpp KPIC_Cam_Observer.cpp
	$(CC) -o Track_Cam_Control Track_Cam_Control.cpp KPIC_Cam_Observer.cpp -lpthread -L$(FLISDK_DIR)/lib/release -lFliSdk -I$(FLISDK_DIR)/include -I$(RELDIR)/include -L$(RELDIR)/lib -lKPIC_shmlib -std=c++11 -lstdc++