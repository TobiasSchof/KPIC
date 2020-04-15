
'''---------------------------------------------------------------------------
Read and write access to shared memory (SHM) structures used by SCExAO

- Author : Frantz Martinache
- Date   : July 12, 2017

Improved version of the original SHM structure used by SCExAO and friends.
---------------------------------------------------------------------------

Named semaphores seems to be something missing from the python API and may 
require the use of an external package.

A possibility:
http://semanchuk.com/philip/posix_ipc/

More info on semaphores:
https://www.mkssoftware.com/docs/man3/sem_open.3.asp
https://docs.python.org/2/library/threading.html#semaphore-objects
'''

import os, sys, mmap, struct
import numpy as np
import astropy.io.fits as pf
from time import time
#import pdb
import posix_ipc
from logging import info #replacing print statements with info 
from atexit import register, unregister
from signal import signal, SIGHUP, SIGTERM
from glob import glob #used for finding semaphores


#The directory where semaphores are stored (set by system, this variable is 
#   used for checking, not for creation.
SEM_DIR = "/dev/shm"

# ------------------------------------------------------
#          list of available data types
# ------------------------------------------------------
all_dtypes = [np.uint8,     np.int8,    np.uint16,    np.int16, 
              np.uint32,    np.int32,   np.uint64,    np.int64,
              np.float32,   np.float64, np.complex64, np.complex128,
              np.bool]

# ------------------------------------------------------
# list of metadata keys for the shm structure (global)
# ------------------------------------------------------
mtkeys = ['imname', 'crtime_sec', 'crtime_nsec', 'latime_sec', 'latime_nsec', 
            'atime_sec', 'atime_nsec', 'cnt0', 'nel', 'size', 'naxis', 'atype', 
            'cnt1']

# ------------------------------------------------------
#    string used to decode the binary shm structure
# ------------------------------------------------------
hdr_fmt = '80s Q Q Q Q Q Q Q I 3H B B B3x' # aligned style


''' 
---------------------------------------------------------
Table taken from Python 2 documentation, section 7.3.2.2.
---------------------------------------------------------

|--------+--------------------+----------------+----------|
| Format | C Type             | Python type    | Std size |
|--------+--------------------+----------------+----------|
| x      | pad byte           | no value       |          |
| c      | char               | string (len=1) |        1 |
| b      | signed char        | integer        |        1 |
| B      | unsigned char      | integer        |        1 |
| ?      | _Bool              | bool           |        1 |
| h      | short              | integer        |        2 |
| H      | unsigned short     | integer        |        2 |
| i      | int                | integer        |        4 |
| I      | unsigned int       | integer        |        4 |
| l      | long               | integer        |        4 |
| L      | unsigned long      | integer        |        4 |
| q      | long long          | integer        |        8 |
| Q      | unsigned long long | integer        |        8 |
| f      | float              | float          |        4 |
| d      | double             | float          |        8 |
| s      | char[]             | string         |          |
| p      | char[]             | string         |          |
| P      | void *             | integer        |          |
|--------+--------------------+----------------+----------| 
'''

class shm:
    def __init__(self, fname:str, data=None, sem:bool=False):
        ''' --------------------------------------------------------------
        Constructor for a SHM (shared memory) object.

        Parameters:
        ----------
        - fname: name of the shared memory file structure
        - data: some array (1, 2 or 3D of data). If an existing file backing is
            pointed to by fname, data will be ignored
        - sem: whether this instance of the shm should create a semaphore

        Depending on whether the file already exists, and/or some new
        data is provided, the file will be created or overwritten.
        -------------------------------------------------------------- '''

        self.fname = fname

        # --------------------------------------------------------------------
        #                dictionary containing the metadata
        # --------------------------------------------------------------------
        self.mtdata = {'imname': '',
                       'crtime_sec': 0,
                       'crtime_nsec': 0,
                       'latime_sec': 0, 
                       'latime_nsec': 0,
                       'atime_sec' : 0,
                       'atime_nsec': 0,
                       'cnt0'  : 0,
                       'nel': 0,
                       'size'  : (0,0,0),
                       'naxis' : 0,
                       'atype': 0,
                       'cnt1'  : 0,}

        # if this file backing already exists, load metadata
        if os.path.isfile(fname):
            info("reading from existing %s" % (fname,))
            self.fd      = os.open(fname, os.O_RDWR)
            self.stats   = os.fstat(self.fd)
            self.buf_len = self.stats.st_size
            self.buf     = mmap.mmap(self.fd, self.buf_len, mmap.MAP_SHARED)
            self.read_meta_data()
            self.select_dtype()        # identify main data-type 
        # otherwise, make name for semaphores
        else:
            spl = fname.split("/")
            if len(spl) > 1: self.mtdata["imname"] = spl[-2]+spl[-1].split(".")[0]
            else: self.mtdata["imname"] = spl[-1].split(".")[0]
        
        #find name of shm for semaphores
        singleName = self.mtdata["imname"]

        #Create lock semaphore
        self.lock = posix_ipc.Semaphore("/"+singleName+"_lock",\
            flags=posix_ipc.O_CREAT, initial_value=1)

        #save start of semaphore name for updating sems later
        self.semName = "/" + singleName + "_sem"

        #first get all semaphores for other processes
        self.semaphores = []
        self.updateSems()

        #If requested, make semaphore for this instance
        if not sem: self.sem = None
        else: 
            free = None
            #find an unused semaphore
            for x in range(0, 100):
                sempath = SEM_DIR + "/sem." + singleName + "_sem"
                if x < 10: sempath += "0"
                sempath += str(x)

                if not os.path.isfile(sempath): 
                    free = x
                    break

            if free is None:
                raise Exception("No free Semaphores. Please clean")

            semName = "/" + singleName + "_sem"
            if free < 10: semName += "0"
            semName += str(free)

            self.sem = posix_ipc.Semaphore(semName, flags = posix_ipc.O_CREAT)
            self.semaphores.append(self.sem)

        msg = '%d semaphores created or re-used'.format(len(self.semaphores))
        info(msg)

        # next create the shm if we have data (we do this after semaphore
        #   creation to alert any waiting processes that this has been created
        if (data is not None) and (not os.path.isfile(fname)):
            info("%s will be created or overwritten" % (fname,))
            self.create(fname, data)

        if (data is None) and (not os.path.isfile(fname)) and (not sem):
            msg = "Either file must exist, data must be provided, or a" + \
                " semaphore must be created."
            raise Exception(msg)

        #automatically perform cleanup
        register(self.close) #handles ctrl-c and exceptions
        signal(SIGHUP, self.close) #handles tmux kill-ses
        signal(SIGTERM, self.close) #handles terminate calls

    def create(self, fname, data):
        ''' --------------------------------------------------------------
        Create a shared memory data structure

        Parameters:
        ----------
        - fname: name of the shared memory file structure
        - data: some array (1, 2 or 3D of data)
        
        Called by the constructor if the provided file-name does not
        exist: a new structure needs to be created, and will be populated
        with information based on the provided data.
        -------------------------------------------------------------- '''
        
        # ---------------------------------------------------------
        # feed the relevant dictionary entries with available data
        # ---------------------------------------------------------
        self.npdtype                = data.dtype

        spl = fname.split("/")
        if len(spl) > 1: self.mtdata["imname"] = spl[-2]+spl[-1].split(".")[0]
        else: self.mtdata["imname"] = spl[-1].split(".")[0]

        self.mtdata['naxis']        = data.ndim
        self.mtdata['size']         = data.shape+((0,)*(3-len(data.shape)))
        self.mtdata['nel']          = data.size
        self.mtdata['atype']        = self.select_atype()
        cur_t = time()
        self.mtdata['crtime_sec']   = int(cur_t)
        self.mtdata['crtime_nsec']  = int((cur_t%1) * 1000000000)
        self.mtdata['cnt0']         = 0
        
        self.select_dtype()

        # ---------------------------------------------------------
        #          reconstruct a SHM metadata buffer
        # ---------------------------------------------------------
        fmts = hdr_fmt.split(' ')
        minibuf = ''.encode()
        for i, fmt in enumerate(fmts):
            #check whether the fmt indicates array (i.e. for size)
            try:
                assert i != 0
                dim = int(fmt[0])
                tpl = self.mtdata[mtkeys[i]]
                minibuf += struct.pack(fmt, *tpl)
            except (ValueError, AssertionError):
                if isinstance(self.mtdata[mtkeys[i]], str):
                    minibuf += struct.pack(fmt, self.mtdata[mtkeys[i]].encode())
                else:
                    minibuf += struct.pack(fmt, self.mtdata[mtkeys[i]])
                
            #set offsets
            if i+1 < len(mtkeys):
                if mtkeys[i+1] == "cnt0": self.c0_offset = len(minibuf)
                if mtkeys[i+1] == "latime_sec": self.latime_offset = len(minibuf)
                if mtkeys[i+1] == "atime_sec": self.atime_offset = len(minibuf)

        self.im_offset = len(minibuf)

        # ---------------------------------------------------------
        #             allocate the file and mmap it
        # ---------------------------------------------------------
        fsz = self.im_offset + self.img_len # file size
        npg = int(fsz / mmap.PAGESIZE) + 1                 # nb pages
        self.fd = os.open(fname, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
        os.write(self.fd, ('\x00' * npg * mmap.PAGESIZE).encode())
        self.buf = mmap.mmap(self.fd, npg * mmap.PAGESIZE, 
                             mmap.MAP_SHARED, mmap.PROT_WRITE)

        # ---------------------------------------------------------
        #              write the information to SHM
        # ---------------------------------------------------------
        self.buf[:self.im_offset] = minibuf # the metadata
        self.set_data(data)
        return(0)

    def rename_img(self, newname):
        ''' --------------------------------------------------------------
        Gives the user a chance to rename the image.

        Parameter:
        ---------
        - newname: a string (< 80 char) with the name
        -------------------------------------------------------------- '''
        
        self.mtdata['imname'] = newname.ljust(80, ' ')
        self.buf[0:80]        = struct.pack('80s', self.mtdata['imname'])

    def close(self):
        ''' --------------------------------------------------------------
        Clean close of a SHM data structure link

        Clean close of buffer, release the file descriptor.
        -------------------------------------------------------------- '''

        #try closing the buffer (the shared memory itself) 
        try: self.buf.close()
        except Exception as ouch: info("Exception on close: {}".format(ouch))

        #if a semaphore was created for this process, unlink it
        if self.sem is not None: 
            try: 
                self.sem.unlink()
                self.sem.close()
            except Exception as ouch: info("Exception on close: {}".format(ouch))

        #close any semaphores opened that we don't own
        try:
            for sem in self.semaphores:
                try: sem.close()
                except Exception as ouch: info("Exception on close: {}".format(ouch))
        except Exception as ouch: info("Exception on close: {}".format(ouch))

        #close the lock semaphore
        try: self.lock.close()
        except Exception as ouch: info("Exception on close: {}".format(ouch))

        #close the underlying file
        try:
            os.close(self.fd)
            self.fd = 0
        except Exception as ouch: info("Exception on close: {}".format(ouch))

        unregister(self.close)

    def updateSems(self):
        '''------------------------------------------------------------------
        Checks the semaphores in self.semaphores. If any have been unlinked,
           close them. If there are any new ones, add them.

        Note: This assumes the naming convention used by CentOS. Before using
           check that a) SEM_DIR is correct and b) if a semaphore is named
           '/xyz' then it is stored as 'sem.xyz'
        -------------------------------------------------------------------'''

        #look for any files in the semaphore directory following the convention
        #  for naming based on the name of this image
        sems = glob(SEM_DIR+"/sem."+self.mtdata["imname"]+"_sem*")
        #create an array to track semaphores to remove while adding new ones
        tmp = [sem.name for sem in self.semaphores]
        
        #add any new semaphores and check if current semaphores are still used
        for sem in sems:
            #strip directories, leaving just file name
            sem = sem[sem.rfind("/")+1:]
            #remove the sem. at the beginning and add '/' to translate to the
            #  name of the semaphore
            sem = "/"+sem[sem.find(".")+1:]
            #check if the semaphore is already being tracked
            try: 
                idx = tmp.index(sem)
                #update tmp to say that this semaphore is still active
                tmp[idx] = None;
            except ValueError:
                #add this semaphore to our list
                self.semaphores.append(posix_ipc.Semaphore(sem, \
                    posix_ipc.O_CREAT))

        #remove any semaphores no longer being used
        #note we iterate in reverse so pops don't affect indices
        for idx, sem in list(enumerate(tmp))[::-1]:
            if not sem is None: self.semaphores.pop(idx).close()

    def read_meta_data(self):
        ''' --------------------------------------------------------------
        Read the metadata fraction of the SHM file.
        Populate the shm object mtdata dictionary.
        -------------------------------------------------------------- '''
        offset = 0
        fmts = hdr_fmt.split(' ')
        for i, fmt in enumerate(fmts):
            if mtkeys[i] == "cnt0": self.c0_offset = offset
            elif mtkeys[i] == "latime_sec": self.latime_offset = offset
            elif mtkeys[i] == "atime_sec": self.atime_offset = offset

            hlen = struct.calcsize(fmt)
            #we have to handle name differently because unpacking doesn't work
            #  correctly on unused bits
            if i == 0:
                #copy the name part of the metadata except 0 bits 
                tmpbuf = [c for c in self.buf[:int(fmt[:fmt.find("s")])] if c!=0]
                dec = struct.unpack("{}s".format(len(tmpbuf)), bytes(tmpbuf))
                self.mtdata['imname'] = dec[0].decode()
            else:
                mdata_bit = struct.unpack(fmt, self.buf[offset:offset+hlen])
                #if the length is only one, we just want to value
                if len(mdata_bit) == 1: self.mtdata[mtkeys[i]] = mdata_bit[0]
                #otherwise we want the whole tuple
                else: self.mtdata[mtkeys[i]] = mdata_bit
            
            offset += hlen

        self.im_offset = offset # offset for the image content

    def load(self) -> bool:
        '''___________________________________________________________________
        Loads the shared memory.

        Returns:
            bool = False if load fails (file doesn't exist or shm already 
                loaded. True if load is successful.
        -------------------------------------------------------------------'''

        # shm is already loaded
        if self.mtdata["crtime_sec"] != 0: return False

        # file backing doesn't exist
        if not os.path.isfile(self.fname): return False

        # otherwise the load should be successful.
        info("reading from existing %s" % (self.fname,))
        self.fd      = os.open(self.fname, os.O_RDWR)
        self.stats   = os.fstat(self.fd)
        self.buf_len = self.stats.st_size
        self.buf     = mmap.mmap(self.fd, self.buf_len, mmap.MAP_SHARED)
        self.read_meta_data()
        self.select_dtype()

        return True

    def print_meta_data(self):
        ''' --------------------------------------------------------------
        Basic printout of the content of the mtdata dictionary.
        -------------------------------------------------------------- '''
        fmts = hdr_fmt.split(' ')
        for i, fmt in enumerate(fmts):
            info(mtkeys[i], self.mtdata[mtkeys[i]])

    def select_dtype(self):
        ''' --------------------------------------------------------------
        Based on the value of the 'atype' code used in SHM, determines
        which numpy data format to use.
        -------------------------------------------------------------- '''
        atype        = self.mtdata['atype']
        self.npdtype = all_dtypes[atype-1]
        self.img_len = self.mtdata['nel'] * self.npdtype().itemsize

    def select_atype(self):
        ''' --------------------------------------------------------------
        Based on the type of numpy data provided, sets the appropriate
        'atype' value in the metadata of the SHM file.
        -------------------------------------------------------------- '''
        for i, mydt in enumerate(all_dtypes):
            if mydt == self.npdtype:
                self.mtdata['atype'] = i+1
        return(self.mtdata['atype'])

    def get_time(self):
        ''' --------------------------------------------------------------
        Read the time the data in the SHM was acquired (UNIX epoch seconds)
        -------------------------------------------------------------- '''
        offset = self.atime_offset
        time = struct.unpack('Q', self.buf[offset:offset+8])[0]
        self.mtdata['atime_sec'] = time
        return(time)

    def set_time(self, latime:float = None, atime:float = None):
        '''--------------------------------------------------------------
        Updates the requested time values in the SHM (atime is write time)
        --------------------------------------------------------------'''
        if not atime is None:
            #rename offset for concision
            off = self.atime_offset

            #get the seconds part of the time
            sec = int(atime)
            #get the nanoseconds part of the time
            nsec = int((atime%1)*1000000000)

            #write the two time parts
            self.buf[off:off+8] = struct.pack('Q', sec)
            self.buf[off+8:off+16] = struct.pack('Q', nsec)

            #update metadata
            self.mtdata['atime_sec'] = sec
            self.mtdata['atime_nsec'] = nsec

        if not latime is None:
            off = self.latime_offset
            sec = int(latime)
            nsec = int((latime%1)*1000000000)
            self.buf[off:off+8] = struct.pack('Q', sec)
            self.buf[off+8:off+16] = struct.pack('Q', nsec)
            self.mtdata['latime_sec'] = sec
            self.mtdata['latime_nsec'] = nsec

    def get_counter(self,):
        ''' --------------------------------------------------------------
        Read the image counter from SHM
        -------------------------------------------------------------- '''
        c0   = self.c0_offset                           # counter offset
        cntr = struct.unpack('Q', self.buf[c0:c0+8])[0] # read from SHM
        self.mtdata['cnt0'] = cntr                      # update object mtdata
        return(cntr)

    def increment_counter(self,):
        ''' --------------------------------------------------------------
        Increment the image counter. Called when writing new data to SHM
        -------------------------------------------------------------- '''
        c0                  = self.c0_offset         # counter offset
        cntr                = self.get_counter() + 1 # increment counter
        self.buf[c0:c0+8]   = struct.pack('Q', cntr) # update SHM file
        self.mtdata['cnt0'] = cntr                   # update object mtdata
        return(cntr)

    def get_data(self, check=False, reform=False):
        ''' --------------------------------------------------------------
        Returns the data part of the shared memory 

        Parameters:
        ----------
        - check: integer (last index) if not False, waits image update
        - reform: boolean, if True, reshapes the array in a 2-3D format
        -------------------------------------------------------------- '''

        i0 = self.im_offset                                  # image offset
        i1 = i0 + self.img_len                               # image end

        #wait for new data
        if check: self.sem.acquire()
        
        #Use a context manager so lock is released if process is killed
        with self.lock:
            data = np.fromstring(self.buf[i0:i1],dtype=self.npdtype) # read img
        #Set last access time to current time
        self.set_time(latime=time())
        
        if reform:
            rsz = self.mtdata['size'][:self.mtdata['naxis']]
            data = np.reshape(data, rsz)
        return(data)

    def set_data(self, data, check_dt=False, atime:float=None):
        ''' --------------------------------------------------------------
        Upload new data to the SHM file.

        Parameters:
        ----------
        - data: the array to upload to SHM
        - check_dt: boolean (default: false) recasts data
        - time: the time (UNIX epoch seconds) that the data was acquired
        Note:
        ----

        The check_dt is available here for comfort. For the sake of
        performance, data should be properly cast to start with, and
        this option not used!
        -------------------------------------------------------------- '''
        #We want to keep acquired time current so get time if none was provided
        if atime is None: atime = time()

        i0 = self.im_offset                                      # image offset
        i1 = i0 + self.img_len                                   # image end
        if check_dt is True:
            #Use context manager so lock is released if process ends
            with self.lock:
                self.buf[i0:i1] = data.astype(self.npdtype()).tostring()
                self.increment_counter()
                #Set last access time to current time and acquired time to the
                #  passed time 
                self.set_time(latime=time(), atime=atime)
        else:
            try:
                #Use context manager so lock is released if process ends
                with self.lock:
                    self.buf[i0:i1] = data.tostring()
                    self.increment_counter()
                    #Set last access time to current time and acquired time to 
                    #  the passed time 
                    self.set_time(latime=time(), atime=atime)
            except:
                info("Warning: writing wrong data-type to shared memory")
                msg = "     shm name: {}".format(self.fname)
                info(msg)
                msg = "     data: {}".format(data)
                return

        self.updateSems()
        for sem in self.semaphores:
            sem.release()

        return

    def save_as_fits(self, fitsname):
        ''' --------------------------------------------------------------
        Convenient sometimes, to be able to export the data as a fits file.
        
        Parameters:
        ----------
        - fitsname: a filename (clobber=True)
        -------------------------------------------------------------- '''
#        pf.writeto(fitsname, self.get_data(), clobber=True)
        return(0)

# =================================================================
# =================================================================
