
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
import asyncio
from logging import info #replacing print statements with info 
from atexit import register
from signal import signal, SIGHUP

# ------------------------------------------------------
#          list of available data types
# ------------------------------------------------------
all_dtypes = [np.uint8,     np.int8,    np.uint16,    np.int16, 
              np.uint32,    np.int32,   np.uint64,    np.int64,
              np.float32,   np.float64, np.complex64, np.complex128]

# ------------------------------------------------------
# list of metadata keys for the shm structure (global)
# ------------------------------------------------------
mtkeys = ['imname', 'crtime_sec', 'crtime_nsec', 'latime_sec', 'latime_nsec', 
            'atime_sec', 'atime_nsec', 'cnt0', 'nel', 'size', 'naxis', 'atype', 
            'cnt1', 'semNb']

# ------------------------------------------------------
#    string used to decode the binary shm structure
# ------------------------------------------------------
hdr_fmt = '80s Q Q Q Q Q Q Q I 3H B B B B'
hdr_fmt_aln = '80s Q Q Q Q Q Q Q I 3H B B B B2x' # aligned style
"""
hdr_fmt = '80s B 3I Q B d d q q B B B H5x Q Q Q B H'
hdr_fmt_pck = '80s B 3I Q B d d q q B B B H5x Q Q Q B H'           # packed style
hdr_fmt_aln = '80s B3x 3I Q B7x d d q q B B B1x H2x Q Q Q B1x H4x' # aligned style
"""



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
    def __init__(self, fname=None, data=None, verbose=False, packed=False, 
        nbkw=0, nbSems:int=1, subSems=[]):
        ''' --------------------------------------------------------------
        Constructor for a SHM (shared memory) object.

        Parameters:
        ----------
        - fname: name of the shared memory file structure
        - data: some array (1, 2 or 3D of data)
        - verbose: optional boolean
        - nbSems: the number of semaphores to create
        - subSems: a list of semaphores that should be updated with this shared
            memory (in addition to any made with nbSems)

        Depending on whether the file already exists, and/or some new
        data is provided, the file will be created or overwritten.
        -------------------------------------------------------------- '''
        #self.hdr_fmt   = hdr_fmt  # in case the user is interested
        #self.c0_offset = 144      # fast-offset for counter #0
        self.packed = packed
        self.nbSems = nbSems
        
        if self.packed:
            self.hdr_fmt = hdr_fmt_pck # packed shm structure
        else:
            self.hdr_fmt = hdr_fmt_aln # aligned shm structure

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
                       'cnt1'  : 0,
                       'semNb' : 0}

        # ---------------
        if fname is None:
            info("No SHM file name provided")
            return(None)

        self.fname = fname
        # ---------------
        # Creating semaphore, *nbSems
        spl = self.fname.split('/')
        if len(spl) > 1: singleName = spl[-2]
        else: singleName = ""

        singleName += spl[-1].split('.')[0]
        self.semaphores = []
        for k in range(nbSems):
            semName = '/'+singleName+'_sem'+'0'+str(k)
            #info('creating semaphore '+semName)
            self.semaphores.append(posix_ipc.Semaphore(semName, \
                flags=posix_ipc.O_CREAT))
        info(str(k)+' semaphores created or re-used')

        #copy any subscription semaphores
        self.subs = subSems

        #Create lock semaphore
        self.lock = posix_ipc.Semaphore("/"+singleName+"_lock", \
            flags=posix_ipc.O_CREAT, initial_value=1)

        # ---------------
        if ((not os.path.exists(fname)) or (data is not None)):
            info("%s will be created or overwritten" % (fname,))
            # the last param is number of keywords
            self.create(fname, data, 0)

        # ---------------
        else:
            info("reading from existing %s" % (fname,))
            self.fd      = os.open(fname, os.O_RDWR)
            self.stats   = os.fstat(self.fd)
            self.buf_len = self.stats.st_size
            self.buf     = mmap.mmap(self.fd, self.buf_len, mmap.MAP_SHARED)
            self.read_meta_data(verbose=verbose)
            self.select_dtype()        # identify main data-type
            self.get_data()            # read the main data
        
        #automatically perform cleanup
        register(self.close) #handles ctrl-c and exceptions
        signal(SIGHUP, self.close) #handles tmux kill-ses

    def create(self, fname, data, nbkw=0):
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
        
        if data is None:
            info("No data (ndarray) provided! Nothing happens here")
            return

        # ---------------------------------------------------------
        # feed the relevant dictionary entries with available data
        # ---------------------------------------------------------
        self.npdtype                = data.dtype
        self.mtdata['imname']       = fname.split('/')[2].split('.')[0]
        self.mtdata['naxis']        = data.ndim
        self.mtdata['size']         = data.shape+((0,)*(3-len(data.shape)))
        self.mtdata['nel']          = data.size
        self.mtdata['atype']        = self.select_atype()
        self.mtdata['semNb']        = self.nbSems
        cur_t = time()
        self.mtdata['crtime_sec']   = int(cur_t)
        self.mtdata['crtime_nsec']  = int((cur_t%1) * 1000000000)
        self.mtdata['cnt0']         = 0
        
        self.select_dtype()

        # ---------------------------------------------------------
        #          reconstruct a SHM metadata buffer
        # ---------------------------------------------------------
        fmts = self.hdr_fmt.split(' ')
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

    def close(self,):
        ''' --------------------------------------------------------------
        Clean close of a SHM data structure link

        Clean close of buffer, release the file descriptor.
        -------------------------------------------------------------- '''
        #try closing the buffer (the shared memory itself) 
        try: self.buf.close()
        #do nothing if buffer doesn't exist or is already closed
        except (OSError, AttributeError): pass

        #as before for semaphores
        try:
            for sem in self.semaphores:
                try: sem.close()
                except OSError: pass
        except AttributeError: pass

        #as before for subscriptions
        try:
            for sem in self.subs:
                try: sem.unlink()
                except (OSError, posix_ipc.ExistentialError): pass
        except AttributeError: pass

        #as before for lock
        try: self.lock.close()
        except (OSError, AttributeError): pass

        #as before for the underlying file
        try:
            os.close(self.fd)
            self.fd = 0
            return(0)
        except (OSError, AttributeError): pass

    def read_meta_data(self, verbose=True):
        ''' --------------------------------------------------------------
        Read the metadata fraction of the SHM file.
        Populate the shm object mtdata dictionary.

        Parameters:
        ----------
        - verbose: (boolean, default: True), prints its findings
        -------------------------------------------------------------- '''
        offset = 0
        fmts = self.hdr_fmt.split(' ')
        for i, fmt in enumerate(fmts):
            if mtkeys[i] == "cnt0": self.c0_offset = offset
            elif mtkeys[i] == "latime_sec": self.latime_offset = offset
            elif mtkeys[i] == "atime_sec": self.atime_offset = offset
            hlen = struct.calcsize(fmt)
            mdata_bit = struct.unpack(fmt, self.buf[offset:offset+hlen])
            #check if data is an array (e.g. size)
            try:
                assert i != 0
                int(fmt[0])
                self.mtdata[mtkeys[i]] = mdata_bit
            except (ValueError, AssertionError):
                self.mtdata[mtkeys[i]] = mdata_bit[0]
            
            offset += hlen

        self.im_offset = offset # offset for the image content

        if verbose:
            self.print_meta_data()

    def print_meta_data(self):
        ''' --------------------------------------------------------------
        Basic printout of the content of the mtdata dictionary.
        -------------------------------------------------------------- '''
        fmts = self.hdr_fmt.split(' ')
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

    def get_data(self, check=False, reform=False, semNb=0):
        ''' --------------------------------------------------------------
        Returns the data part of the shared memory 

        Parameters:
        ----------
        - check: integer (last index) if not False, waits image update
        - reform: boolean, if True, reshapes the array in a 2-3D format
        -------------------------------------------------------------- '''
        i0 = self.im_offset                                  # image offset
        i1 = i0 + self.img_len                               # image end

        if check is not False:
            self.semaphores[semNb].acquire()
        
        #Acquire the lock
        self.lock.acquire()
        data = np.fromstring(self.buf[i0:i1],dtype=self.npdtype) # read img
        #Release the lock
        self.lock.release()
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
            #Acquire the lock
            self.lock.acquire()
            self.buf[i0:i1] = data.astype(self.npdtype()).tostring()
            #Release the lock
            self.lock.release()
            #Set last access time to current time and acquired time to the
            #  passed time 
            self.set_time(latime=time(), atime=atime)
        else:
            try:
                #Acquire the lock
                self.lock.acquire()
                self.buf[i0:i1] = data.tostring()
                #Release the lock
                self.lock.release()
                #Set last access time to current time and acquired time to the
                #  passed time 
                self.set_time(latime=time(), atime=atime)
            except:
                info("Warning: writing wrong data-type to shared memory")
                return
        self.increment_counter()
        for sem in self.semaphores:
            sem.release()

        for sem in self.subs:
            #since it's assume subscriptions are only for one user, 
            #  subscriptions sems are bounded at 1.
            if sem.value == 0: sem.release()

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
