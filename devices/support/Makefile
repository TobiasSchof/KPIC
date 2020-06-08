# NIRSPEC fiber injection unit. Build device support scripts

override SYSNAM = kss/nirspec/nsfiu/devices/support
override VERNUM = 1.0

# If I knew that code would not work with Python 2 I would:
##override ENABLE_PYTHON2 = False
## DIRS = designer

SOURCE = linksem.c shmlib.cpp

RELLIB = dev_Exceptions.py shmlib.py Conex.py libshmlib.so shmlib.hpp
RELBIN = linksem
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


#C compilations
linksem: linksem.c
	$(CC) -o linksem linksem.c -lpthread
libshmlib.so: shmlib.cpp
    $(CC) -shared -o libshmlib.so -fPIC shmlib.cpp
