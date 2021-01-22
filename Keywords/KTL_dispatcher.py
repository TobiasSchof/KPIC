#!/usr/env/bin kpython3

import DFW
from time import sleep

from FIU_TTM_Keywords import FIU_TTM_POS_X_KTL


def setupkeywords(service):

    FIU_TTM_POS_X_KTL("TTMPOSX", service)

try:
    service = DFW.Service("nsfiu", "/home/nfiudev/dev/Keywords/stdiosvc.conf", setupkeywords)
    while True: sleep(1)
except:
    service.shutdown()
    service = None