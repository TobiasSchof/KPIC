
import shmlib_sce as shmlib
import time

a=shmlib.shm('/tmp/ircam0.im.shm')

t0=time.time()
for k in range(0,100):
    a.get_data(check=True)

print(k/(time.time()-t0))
