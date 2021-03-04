
'''---------------------------------------------------------------------------
Read and write access to shared memory (SHM) structures used by KPIC
---------------------------------------------------------------------------'''

import os, sys, struct
from mmap import mmap as Mmap, MAP_SHARED
from time import time
from logging import info
from atexit import register, unregister
from signal import signal, SIGHUP, SIGTERM
from glob import glob

# installs
import posix_ipc as ipc
import numpy as np
import astropy.io.fits as pf

#The directory where semaphores are stored (set by system, this variable is 
#   used for checking, not for creation.
SEM_DIR = "/dev/shm"

# ------------------------------------------------------
#          list of available data types
# ------------------------------------------------------
# Dictionaries to translate between metadata type and numpy type
atod = { 1 : np.dtype("uint8"), 2 : np.dtype("int8"), 3 : np.dtype("uint16"), 
         4 : np.dtype("int16"), 5 : np.dtype("uint32"), 6 : np.dtype("int32"),
         7 : np.dtype("uint64"), 8 : np.dtype("int64"), 9 : np.dtype("float32"),
         10 : np.dtype("float64"), 11 : np.dtype("complex64"), 
         12 : np.dtype("complex128"), 13 : np.dtype("<U1")}  
dtoa = { value : key for (key, value) in atod.items() } 

# the size of each of the data types
asize = { 1 : 1, 2 : 1, 3 : 2, 4 : 2, 5 : 4, 6 : 4, 7 : 8, 8 : 8, 9 : 8, 
          10 : 16, 11 : 16, 12 : 32, 13 : 4} 

# ------------------------------------------------------
# list of metadata keys for the shm structure (global)
# ------------------------------------------------------
mtkeys = ['imname', 'crtime_sec', 'crtime_nsec', 'atime_sec', 'atime_nsec', 
          'cnt0', 'nel', 'size', 'naxis', 'atype', 'mmap', 'croppable']

# ------------------------------------------------------
#    string used to decode the binary shm structure
# ------------------------------------------------------
# See the following link for format character translation:
#    https://docs.python.org/2/library/struct.html#format-characters
hdr_fmt = '80s Q Q Q Q Q I 3H B B B B 2x'

class Shm:

    class ExistentialError(Exception):
        pass

    class SemaphoreError(Exception):
        pass

    def __init__(self, fname:str, data:np.ndarray=None, mmap:bool=False, croppable:bool=False,
                 sem:bool=False):
        ''' --------------------------------------------------------------
        Constructor for a SHM (shared memory) object.

        Parameters:
        ----------
        - fname: name of the shared memory file structure
        - data: some array (1, 2 or 3D of data). If an existing file backing is
            pointed to by fname, data will be ignored
        - mmap: whether this shm should be mmapped. Mmapping speeds up read
            and write but takes up memory.
        - croppable: whether this data is croppable or a constant size
        - sem: whether this instance of the shm should create a semaphore

        If data is provided, but a file with the given name already exists,
           the data will be ignored and the existing file will be used.
        -------------------------------------------------------------- '''

        # if a string as passed in, convert it to a numpy array
        if type(data) is str:
            data = np.array([char for char in data], np.dtype("<U1"))
            croppable = True
        elif str(data.dtype) == "<U1": croppable = True
        elif str(data.dtype).find("<U") == 0:
            # in this case, we have a string but it's not broken into chars
            # so reform array into string
            nel = 1
            for dim in data.shape:
                if dim != 0: nel *= dim
            data.reshape((nel,))
            data = ("{}"*nel).format(*data) 
            # and then put back in an array
            data = np.array([char for char in data], np.dtype("<U1")) 
            croppable = True

        self.fname = fname
        self.mmap = None

        # --------------------------------------------------------------------
        #                dictionary containing the metadata
        # --------------------------------------------------------------------
        self.mtdata = {'imname': '',
                       'crtime_sec': 0,
                       'crtime_nsec': 0,
                       'atime_sec' : 0,
                       'atime_nsec': 0,
                       'cnt0'  : 0,
                       'nel': 0,
                       'size'  : (0,0,0),
                       'naxis' : 0,
                       'atype': 0,
                       'mmap'  : 0,
                       'croppable' : 0}

        # if file doesn't exist, see if we need to make it
        if not os.path.isfile(fname):
            if data is not None:
                info("{} will be created".format(fname))
                self.create(fname, data, mmap, croppable)
            # if there's no file, no data, and no semaphore, this class is
            #   probably a mistake
            elif not sem:
                msg = "Either file must exist, data must be provided, or a" +\
                      " semaphore must be created."
                raise Shm.ExistentialError(msg)

        # if the file exists, load info
        if os.path.isfile(fname):
            info("reading from existing %s" % (fname,))
            # read metadata
            self.read_meta_data()

            # mmap or dont, as requested
            if self.mmap:
                with open(self.fname, "rb+") as file_:
                    # get size of file to mmap
                    buf_len = os.fstat(file_.fileno()).st_size
                    self.buf = Mmap(file_.fileno(), buf_len, MAP_SHARED)
        # otherwise, we want a semaphore so make imname
        else:
            spl = self.fname.split("/")
            # We make image name from the directory and filename w/o extension
            if len(spl) > 1: 
                self.mtdata["imname"] = spl[-2]+spl[-1].split(".")[0]
            # unless there is no directory
            else: self.mtdata["imname"] = spl[-1].split(".")[0]

        #Create lock semaphore
        self.lock = ipc.Semaphore("/"+self.mtdata["imname"]+"_lock",
            flags=ipc.O_CREAT, initial_value=1)

        #If requested, make semaphore for this instance
        self.sem = None
        if sem: self.find_sem()

        #automatically perform cleanup
        register(self.close) #handles ctrl-c and exceptions
        signal(SIGHUP, self.signal_handler) #handles tmux kill-ses
        signal(SIGTERM, self.signal_handler) #handles terminate calls

    def find_sem(self):
        '''--------------------------------------------------------------
        Tries to connect to an unused semaphore of this shm if this shm 
        doesn't already have a semaphore.
        --------------------------------------------------------------'''

        #find an unused semaphore
        for x in range(0, 100):
            semName = "/" + self.mtdata["imname"] + "_sem"
            if x < 10: semName += "0"
            semName += str(x)

            # the CREX tag tries to create a semaphore and throws an
            #   error if a semaphore with the given name already exists 
            try:
                self.sem = ipc.Semaphore(semName, flags=ipc.O_CREX)
                break
            except ipc.ExistentialError: pass

        if self.sem is None:
            msg = "No free Semaphore available. Please clean processes."
            raise Shm.SemaphoreError(msg)

    def create(self, fname:str, data:np.ndarray, mmap:bool, croppable:bool):
        ''' --------------------------------------------------------------
        Creates a file backing for a shared memory structure

        Parameters:
        ----------
        - fname: name of the shared memory file structure
        - data: some array (1, 2 or 3D of data)
        - mmap: whether this shm should be marked as one to mmap
        - croppable: whether this data can be cropped
        
        Called by the constructor if the provided file-name does not
        exist: a new structure needs to be created, and will be populated
        with information based on the provided data.
        -------------------------------------------------------------- '''
        
        # ---------------------------------------------------------
        # feed the relevant dictionary entries with available data
        # ---------------------------------------------------------
        spl = self.fname.split("/")
        # We make image name from the directory and filename w/o extension
        if len(spl) > 1: 
            self.mtdata["imname"] = spl[-2]+spl[-1].split(".")[0]
        # unless there is no directory
        else: self.mtdata["imname"] = spl[-1].split(".")[0]
        
        self.mtdata['naxis']        = data.ndim
        self.mtdata['size']         = data.shape+((0,)*(3-len(data.shape)))
        self.mtdata['nel']          = data.size
        self.mtdata['atype']        = dtoa[data.dtype] 
        cur_t = time()
        self.mtdata['crtime_sec']   = int(cur_t)
        self.mtdata['crtime_nsec']  = int((cur_t%1) * 1000000000)
        self.mtdata['cnt0']         = 0
        self.mtdata['mmap']         = mmap
        self.mtdata['croppable']    = croppable
        
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
            except (ValueError, AssertionError, IndexError):
                if fmt.endswith("x"):
                    minibuf += struct.pack(fmt)
                elif isinstance(self.mtdata[mtkeys[i]], str):
                    minibuf += struct.pack(fmt, self.mtdata[mtkeys[i]].encode())
                else:
                    minibuf += struct.pack(fmt, self.mtdata[mtkeys[i]])

        with open(self.fname, "wb+") as backing:
            backing.write(minibuf+data.astype(data.dtype).tostring())

        self.post_sems()

    def read_meta_data(self):
        ''' --------------------------------------------------------------
        Read the metadata fraction of the SHM file.
        Populate the shm object mtdata dictionary.
        Sets offsets based on the format variable above
        -------------------------------------------------------------- '''
        offset = 0
        fmts = hdr_fmt.split(' ')
        with open(self.fname, "rb") as backing:
            buf = backing.read()
            for i, fmt in enumerate(fmts):
                # ignore padding bytes
                if fmt.endswith("x"): 
                    hlen = struct.calcsize(fmt)
                    struct.unpack(fmt, buf[offset:offset+hlen])
                    offset += hlen
                    continue

                if mtkeys[i] == "cnt0": self.c0_offset = offset
                elif mtkeys[i] == "atime_sec": self.atime_offset = offset
                elif mtkeys[i] == "size": self.sz_offset = offset

                hlen = struct.calcsize(fmt)
                # we have to handle name differently because unpacking doesn't
                #   work correctly on unused bits
                if i == 0:
                    #copy the name part of the metadata except 0 bits 
                    name = [c for c in buf[:int(fmt[:fmt.find("s")])] if c!=0]
                    dec = struct.unpack("{}s".format(len(name)), bytes(name))
                    self.mtdata['imname'] = dec[0].decode()
                else:
                    item = struct.unpack(fmt, buf[offset:offset+hlen])
                    #if the length is only one, we just want value
                    if len(item) == 1: self.mtdata[mtkeys[i]] = item[0]
                    #otherwise we want the whole tuple
                    else: self.mtdata[mtkeys[i]] = item
                
                offset += hlen

        # offset for data
        self.im_offset = offset

        self.mmap = bool(self.mtdata["mmap"])
        self.croppable = bool(self.mtdata["croppable"])
        self.npdtype = atod[self.mtdata["atype"]]

    def close(self):
        ''' --------------------------------------------------------------
        Clean close of a SHM data structure link

        Clean close of buffer, release the file descriptor.
        -------------------------------------------------------------- '''

        # if we mmapped, close the mmap buffer
        if self.mmap:
            try: self.buf.close()
            except Exception as ouch: 
                info("Exception on close: {}".format(ouch))

        # if a semaphore was created for this process, unlink it
        if self.sem is not None: 
            try: 
                self.sem.unlink()
                self.sem.close()
            except Exception as ouch: 
                info("Exception on close: {}".format(ouch))

        # unregister this method to avoid duplicate closes
        unregister(self.close)

    def signal_handler(self, signum, stack):
        if self.sem is not None:
            try: self.sem.release()
            except: pass 

    def post_sems(self):
        '''------------------------------------------------------------------
        Connects to any semaphores in SEM_DIR named with this shm's imname
           and updates them.

        NOTE: This assumes the naming convention used by CentOS. Before using
           check that a) SEM_DIR is correct and b) if a semaphore is named
           '/xyz' then it is stored as 'sem.xyz'

        The reason that semaphores are opened and closed rather than stored is
           to ensure that semaphores recycled between postings are handled
           correctly. 
        -------------------------------------------------------------------'''

        # look for any files in the semaphore directory following the convention
        #    for naming based on the name of this image
        sems = glob(SEM_DIR+"/sem."+self.mtdata["imname"]+"_sem*")

        # connect to sem, increment it, close it
        for sem in sems:
            # strip directories from filename
            sem_nm = sem[sem.rfind("/")+1:]
            # remove sem. at beginning and add '/'
            sem_nm = "/"+sem_nm[4:]
            # connect to semaphore
            sem = ipc.Semaphore(sem_nm, ipc.O_CREAT)
            # increment semaphore
            sem.release()
            # close semaphore
            sem.close()


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

        # read metadata
        self.read_meta_data()

        # mmap or dont, as metadata reflects
        if self.mmap:
            with open(self.fname, "rb+") as file_:
                # get size of file to mmap
                buf_len = os.fstat(file_.fileno()).st_size
                self.buf = Mmap(file_.fileno(), buf_len, MAP_SHARED)

        return True

    def get_time(self) -> float:
        ''' --------------------------------------------------------------
        Read the time the data in the SHM was acquired (UNIX epoch seconds)
        -------------------------------------------------------------- '''
        sec_o = self.atime_offset
        nsec_o = sec_o + 8
        if self.mmap:
            with self.lock:
                sec = struct.unpack('Q', self.buf[sec_o:nsec_o])[0]
                nsec = struct.unpack("Q", self.buf[nsec_o:nsec_o+8])[0]
        else:
            with self.lock, open(self.fname, "rb") as file_:
                buf = file_.read()
                sec = struct.unpack('Q', buf[sec_o:nsec_o])[0]
                nsec = struct.unpack("Q", buf[nsec_o:nsec_o+8])[0]

        self.mtdata['atime_sec'] = sec
        self.mtdata['atime_nsec'] = nsec
        return sec + (nsec * (10**(-9))) 

    def get_counter(self,):
        ''' --------------------------------------------------------------
        Read the image counter from SHM
        -------------------------------------------------------------- '''
        c0   = self.c0_offset
        if self.mmap: 
            with self.lock:
                cntr = struct.unpack('Q', self.buf[c0:c0+8])[0]
        else:
            with self.lock, open(self.fname, "rb") as file_:
                buf = file_.read()
                cntr = struct.unpack('Q', buf[c0:c0+8])[0]

        self.mtdata['cnt0'] = cntr
        return(cntr)

    def get_size(self):
        ''' --------------------------------------------------------------
        Read the image size from SHM
        -------------------------------------------------------------- '''

        offset = self.sz_offset
        if self.mmap: 
            with self.lock:
                # get most recent size
                sz = struct.unpack('3H', self.buf[offset:offset+6])[:]
                # get most recent naxis
                nax = struct.unpack("B", self.buf[offset+6:offset+7])[0]
        else:
            with self.lock, open(self.fname, "rb") as file_:
                buf = file_.read()
                sz = struct.unpack('3H', buf[offset:offset+6])[:]
                nax = struct.unpack("B", buf[offset+6:offset+7])[0]

        self.mtdata["size"] = sz
        self.mtdata["naxis"] = nax
        return(sz)

    def get_data(self, check=False, reform=False):
        ''' --------------------------------------------------------------
        Returns the data part of the shared memory 

        Parameters:
        ----------
        - check: integer (last index) if not False, waits image update
        - reform: boolean, if True, reshapes the array in a 2-3D format
                    or into a string if dypte is <U1
        -------------------------------------------------------------- '''

        #wait for new data
        if check: 
            if self.sem is None: self.find_sem()

            self.sem.acquire()

        # try to get beginning of image
        try:
            i0 = self.im_offset
        # Attribute Error means we haven't loaded the shm
        except AttributeError:
            self.load()
            i0 = self.im_offset

        if self.mtdata["croppable"]:
            self.read_meta_data()

        # short name for the end of the data
        i1 = i0 + self.mtdata["nel"]*asize[self.mtdata["atype"]]
        # short name for the cnt0 offset
        c0   = self.c0_offset

        #Use a context manager so lock is released if process is killed
        if self.mmap:
            with self.lock:
                data = np.fromstring(self.buf[i0:i1],dtype=self.npdtype)
                cntr = struct.unpack('Q', self.buf[c0:c0+8])[0]
        else:
            with self.lock, open(self.fname, "rb") as file_:
                buf = file_.read()
                data = np.fromstring(buf[i0:i1],dtype=self.npdtype)
                cntr = struct.unpack('Q', buf[c0:c0+8])[0]

        # update counter
        self.mtdata["cnt0"] = cntr

        # if requested, reshape data
        if reform:
            if self.npdtype == "<U1":
                data = ("{}"*self.mtdata["nel"]).format(*data)
            else:
                rsz = self.mtdata['size'][:self.mtdata['naxis']]
                # if there's an x and y axis, flip them (row, column vs width, height)
                if self.mtdata['naxis'] >= 2:
                    rsz = (rsz[1], rsz[0], *rsz[2:len(rsz)]) 
                data = np.reshape(data, rsz)

        return data

    def set_data(self, data:np.ndarray, atime:float=None):
        ''' --------------------------------------------------------------
        Upload new data to the SHM file.

        Parameters:
        ----------
        - data:  the array to upload to SHM
        - time:  the time (UNIX epoch seconds) that the data was acquired
        Note:
        ----
        -------------------------------------------------------------- '''

        # if a string as passed in, convert it to a numpy array
        if type(data) is str:
            data = np.array([char for char in data], np.dtype("<U1"))
        # if array of strings, break into array of chars
        elif str(data.dtype).find("<U") == 0 and str(data.dtype) != "<U1":
            # in this case, we have a string but it's not broken into chars
            # so reform array into string
            nel = 1
            for dim in data.shape:
                if dim != 0: nel *= dim
            data.reshape((nel,))
            data = ("{}"*nel).format(*data) 
            # and then put back in an array
            data = np.array([char for char in data], np.dtype("<U1")) 
       
        #We want to keep acquired time current so get time if none was provided
        if atime is None: atime = time()
        #get the seconds part of the time
        sec = int(atime)
        #get the nanoseconds part of the time
        nsec = int((atime%1) * 10**9)

        resize = False
        # if the size of the new data doesn't match current size, change it
        if self.mtdata["croppable"]:
            if len(data.shape) >= 2:
                sz = list(data.shape)
                sz[0] = sz[1]
                sz[1] = data.shape[0]
            else: sz = list(data.shape)
            if len(sz) < 3:
                sz += [0]*(3-len(sz))
            if self.mtdata["size"] != sz:
                if len(sz) <= 3:
                    self.mtdata["size"] = list(sz) + [0]*(3 - len(sz))
                # shms of up to 3 axes are supported
                else:
                    self.mtdata["size"] = list(sz[:3])
                self.mtdata["nel"] = 1
                for dim in self.mtdata["size"]: 
                    if dim != 0: self.mtdata["nel"] *= dim
                resize = True

        # start of the data
        i0 = self.im_offset
        # end of the data
        i1 = i0 + self.mtdata["nel"]*asize[self.mtdata["atype"]] 
        # start of cnt0
        c0 = self.c0_offset
        # start of atime
        at = self.atime_offset

        if self.mmap:
            with self.lock:
                # write the data
                self.buf[i0:i1] = data.tostring()
                # write the two atime parts
                self.buf[at:at+8] = struct.pack('Q', sec)
                self.buf[at+8:at+16] = struct.pack('Q', nsec)
                # get last cnt0
                cntr = struct.unpack('Q', self.buf[c0:c0+8])[0] + 1
                # write cnt0 increment
                self.buf[c0:c0+8]   = struct.pack('Q', cntr)
                # if necessary, write size and nel
                if resize:
                    # nel is the 4 bytes before size
                    self.buf[self.sz_offset-4:self.sz_offset] = struct.pack("I", self.mtdata["nel"])
                    self.buf[self.sz_offset:self.sz_offset+6] = struct.pack("3H", *self.mtdata["size"])
        else:
            with self.lock, open(self.fname, "rb+") as file_:
                # get file contents
                buf = list(file_.read())
                # write the data
                buf[i0:i1] = data.tostring()
                # write the two atime parts
                buf[at:at+8] = struct.pack('Q', sec)
                buf[at+8:at+16] = struct.pack('Q', nsec)
                # get last cnt0
                cntr = struct.unpack('Q', bytes(buf)[c0:c0+8])[0] + 1
                # write cnt0 increment
                buf[c0:c0+8]   = struct.pack('Q', cntr)
                # if necessary, write size and nel
                if resize:
                    # nel is the 4 bytes before size
                    buf[self.sz_offset-4:self.sz_offset] = struct.pack("I", self.mtdata["nel"])
                    buf[self.sz_offset:self.sz_offset+6] = struct.pack("3H", *self.mtdata["size"])
                # write updates
                file_.seek(0)
                file_.write(bytes(buf))

        #update metadata
        self.mtdata['atime_sec'] = sec
        self.mtdata['atime_nsec'] = nsec
        self.mtdata["cnt0"] = cntr

        self.post_sems()

        return

    def save_as_fits(self, fitsname):
        ''' --------------------------------------------------------------
        Convenient sometimes, to be able to export the data as a fits file.
        
        Parameters:
        ----------
        - fitsname: a filename (clobber=True)
        -------------------------------------------------------------- '''
        pf.writeto(fitsname, self.get_data(), clobber=True)
        return(0)

# =================================================================
# =================================================================
