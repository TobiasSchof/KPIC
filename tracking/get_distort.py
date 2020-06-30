import sys
from time import sleep

sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")
from sce_shmlib import shm

sep = shm("/tmp/Tracking/SEP.im.shm")
pa  = shm("/tmp/Tracking/PA.im.shm")

def get_dis_sep():
    return sep.get_data()[1]

def get_dis_pa():
    return pa.get_data()[1]

def set_pa(pa:float, ret:bool=False):
    data = pa.get_data()
    data[0] = pa
    pa.set_data(data)
    if ret:
        cnt = pa.mtdata["cnt0"]
        while(pa.get_counter() == cnt): sleep(2)

def set_sep(sep:float, ret:bool=False):
    data = sep.get_data()
    data[0] = sep
    sep.set_data(data)
    if ret:
        cnt = sep.mtdata["cnt0"]
        while(sep.get_counter() == cnt): sleep(2)
