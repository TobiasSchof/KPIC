# NIRSPEC fiber injection unit. Build device support scripts

override SYSNAM = kss/nirspec/nsfiu/devices/support
override VERNUM = 1.0

SOURCE = linksem.c KPIC_shmlib.cpp
RELINCLUDE = KPIC_shmlib.hpp
RELLIB = libKPIC_shmlib.so
RELBIN = linksem

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


#C compilations
linksem: linksem.c
	$(CC) -o linksem linksem.c -lpthread
libKPIC_shmlib.so: KPIC_shmlib.cpp
	$(CC) -shared -o libKPIC_shmlib.so -fPIC KPIC_shmlib.cpp -lstdc++fs
