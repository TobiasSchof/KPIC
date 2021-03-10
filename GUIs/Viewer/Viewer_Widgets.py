# standard libraries
from time import time, sleep
import os

# installs
from PyQt5.QtWidgets import QLineEdit, QFrame, QComboBox, QCheckBox, QWidget, QPushButton, QFileDialog, QDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QTimer, QSize, QTemporaryDir, QFile, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QImage, QValidator, QIntValidator, QDoubleValidator, QFont
from PyQt5 import uic
from PIL import Image
from astropy.io import fits
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients
import pyqtgraph as pg
import numpy as np

# nfiuserver libraries
from KPIC_shmlib import Shm
from Viewer import Shm_Watcher
import resources.images

resource_path = os.path.dirname(__file__)+"/resources"

####### Thumbnail View #######

class Img(pg.GraphicsView):
    """A widget to display the image and maintain aspect ratio while changing size"""

    def __init__(self, *args, refresh_rate:int = 40, **kwargs):
        """Constructor
        
        Args:
            refresh_rate = the number of milliseconds to wait before refreshing widget
            """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a placeholder for greyscale map
        self.no_lup = None

        # set a single-shot timer to setup the image widget
        self.setup_timer = QTimer()
        self.setup_timer.setSingleShot(True)
        self.setup_timer.timeout.connect(self.setup)
        self.setup_timer.start(10)

    def setup(self):
        """Sets up the image view and puts in a placeholder image"""

        # get a pyqtgraph viewbox
        self.vb = pg.ViewBox()
        # make the viewbox this central item
        self.setCentralItem(self.vb)
        # lock aspect ratio
        self.vb.setAspectLocked()
        # put an image item in this viewbox
        self.img = pg.ImageItem()
        self.vb.addItem(self.img)
        # extract placeholder image
        tempDir = QTemporaryDir()
        tmpfile = tempDir.path() + "/placeholder.jpg"
        QFile.copy(":/placeholder/no_img.jpg", tmpfile)
        self.placeholder = Image.open(tmpfile)
        # image comes in rotated, so rotate to correct orientation
        self.placeholder = self.placeholder.rotate(270)
        # convert to numpy array
        self.placeholder = np.array(self.placeholder.getdata()).reshape(self.placeholder.size[1],
            self.placeholder.size[0], 3)
        self.img.setImage(self.placeholder)
        # delete temporary dir
        tempDir.remove()
        tempDir = None
        tmpfile = None

        # a variable to store the currently active gradient widget
        self.grad_widg = None

        # variable to store the different image shms
        #   (can be switched by changing the value of self.Img_Shm)
        self.raw_im  = "/tmp/Track_Cam/RAWIMG.im.shm"
        try: self.raw_im = Shm(self.raw_im)
        except: pass
        self.proc_im = "/tmp/Vis_Process/PROCIMG.im.shm"
        try: self.proc_im = Shm(self.proc_im)
        except: pass

        # connect to shm
        self.Img_shm = self.proc_im

        # create Label to display current coordinates
        self.cur_pix = pg.TextItem(color = "w", fill = pg.mkBrush(color="k"))
        self.cur_pix.setFont(QFont("not set", pointSize = 10))
        self.addItem(self.cur_pix)

        self.stats = pg.TextItem(color = "w", fill = pg.mkBrush(color="k"), anchor=(1, 0))
        self.stats.setFont(QFont("not set", pointSize = 10))
        # set position to top right
        self.stats.setPos(self.width()-1, 0)
        # set position to move to top right on resize
        self.addItem(self.stats)

        # variable to hold position of mouse, if it's hovering over image
        self.mousePos = None

        # connect mouseMoved item to mouseover event on image
        self.scene().sigMouseMoved.connect(self.mouseMoved)

        # variables to store min/max
        self.min     = 0
        self.max     = 16000
        self.automin = True
        self.automax = True

        # start a repeating timer to trigger updates for images and labels
        self.setup_timer = None
        self.img_timer = QTimer()
        self.lbl_timer = QTimer()

        # save starting zoom
        self.base_zm = self.vb.getState()["viewRange"]

        self.img_timer.timeout.connect(self.img_update)
        self.img_timer.start(self.refresh_rate)

        self.lbl_timer.timeout.connect(self.lbl_update)
        self.lbl_timer.start(500)

    def resizeEvent(self, *args, **kwargs):
        """Repositions stats label when window is resized"""

        super().resizeEvent(*args, **kwargs)
        try: self.stats.setPos(self.width()-1, 0)
        except: pass

    def leaveEvent(self, QEvent):
        """A mthod to handle when the mouse leaves the image view
        
        Hides the current pixel label if it is not already hidden
        """

        if self.cur_pix.isVisible(): self.cur_pix.hide()
        self.mousePos = None

    def mouseMoved(self, event):
        """A method to update the tooltip with pixel location and intensity"""

        # get view coordinates from scene coordinates
        mousePoint = self.vb.mapSceneToView(event)
        # get image coordinates from view coordinates
        mousePoint = self.vb.mapFromViewToItem(self.img, mousePoint)
        x = int(mousePoint.x())
        y = int(mousePoint.y())
        # if coordinates are within bounds, set tool tip
        if 0 <= x < self.img.image.shape[0] and 0 <= y < self.img.image.shape[1]:
            self.mousePos = (x, y)
        else: self.mousePos = None

    def img_update(self):
        """Method to try to fetch a new image"""

        # set new image
        try:
            if type(self.Img_shm) is str:
                try: self.raw_im = Shm(self.raw_im)
                except: pass
                try: self.proc_im = Shm(self.proc_im)
                except: pass

                self.Img_shm = Shm(self.Img_shm)

            self.Img_shm.read_meta_data()
            # if image is at least two minutes old, use placeholder
            if time() - self.Img_shm.mtdata["atime_sec"] > 120: assert 0 == 1

            img = self.Img_shm.get_data(reform = True)
            # if getting a raw image, overwrite the first four pixels (tags)
            try:
                if self.Img_shm.fname == self.raw_im.fname:
                    img[0,:4] = img[0,4]
            except: pass

            # save auto min/max
            if self.automin:
                self.min = img.min()
            if self.automax:
                self.max = img.max()

            # clip if not auto
            if not self.automin or not self.automax:
                img = np.clip(img, None if self.automin else self.min,
                    None if self.automax else self.max)

            self.img.setImage(np.rot90(img))
        except:
            if type(self.Img_shm) is not str and not os.path.exists(self.Img_shm.fname):
                self.Img_shm = self.Img_shm.fname

            self.img.setImage(self.placeholder)
        
    def lbl_update(self):
        """Method to set label text""" 

        # deal with current position text label
        if not self.mousePos is None:
            intensity = self.img.image[self.mousePos[0]][self.mousePos[1]]
            # placeholder image has RGB values
            if type(intensity) is np.ndarray: intensity = "---"
            self.cur_pix.setHtml("({x:d}, {y:d}): <b>{intensity}</b>".format(x = self.mousePos[0], 
               y = self.mousePos[1], intensity = intensity))
            if not self.cur_pix.isVisible(): self.cur_pix.show() 
        elif self.cur_pix.isVisible(): self.cur_pix.hide()

        # deal with min/max label
        try: self.stats.setHtml("min: <b>{:d}</b> max: <b>{:d}</b>".format(self.min, self.max))
        except: self.stats.setHtml("min: <b>---</b> max: <b>---</b>")

class Save_raw(QPushButton):
    """A class to save a raw frame"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        self.proc = self.parent().proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""

        # try to get an image
        try:
            img = self.proc.grab_n(1, "raw")
        except:
            dlg = QMessageBox()
            dlg.setWindowTitle("Uh oh!")
            dlg.setText("No image found. Please check that the camera is on.")
            dlg.exec_()
            return

        try:
            filedialog = QFileDialog(self)
            # set to select save file
            filedialog.setAcceptMode(QFileDialog.AcceptSave)
            # set default suffix to .fits
            filedialog.setDefaultSuffix("fits")
            # start dialog in /nfiudata directory
            filedialog.setDirectory("/nfiudata")
            # show that we're using .fits in filetype selection
            filedialog.setNameFilters(["FITS (*.fits)"])
            # if window was accepted
            if (filedialog.exec()):
                # pull filename
                filename = filedialog.selectedFiles()[0]
                # save file 
                img.writeto(filename, overwrite=True)
        except:
            dlg = QMessageBox()
            dlg.setWindowTitle("Uh oh!")
            dlg.setText("There was a problem saving the image.")
            dlg.exec_()
            return

class Save_proc(QPushButton):
    """A class to save a processed frame"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        self.proc = self.parent().proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""

        # try to get an image
        try:
            img = self.proc.grab_n(1, "vis")
        except:
            dlg = QMessageBox()
            dlg.setWindowTitle("Uh oh!")
            dlg.setText("No image found. Please check that the camera is on and that the processing script is processing.")
            dlg.exec_()
            return

        try:
            filedialog = QFileDialog(self)
            # set to select save file
            filedialog.setAcceptMode(QFileDialog.AcceptSave)
            # set default suffix to .fits
            filedialog.setDefaultSuffix("fits")
            # start dialog in /nfiudata directory
            filedialog.setDirectory("/nfiudata")
            # show that we're using .fits in filetype selection
            filedialog.setNameFilters(["FITS (*.fits)"])
            # if window was accepted
            if (filedialog.exec()):
                # pull filename
                filename = filedialog.selectedFiles()[0]
                # save file 
                img.writeto(filename, overwrite=True)
        except:
            dlg = QMessageBox()
            dlg.setWindowTitle("Uh oh!")
            dlg.setText("There was a problem saving the image.")
            dlg.exec_()
            return

class Save_block(QPushButton):
    """A class to save a raw frame"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        self.proc = self.parent().proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""

        settings = Save_block.Save_block_popup()
        values = settings.getResults()

        try:
            img = self.proc.grab_n(values[2], values[0], end_header = values[1] == 0,
                header_per = values[1])
        except:
            dlg = QMessageBox()
            dlg.setWindowTitle("Uh oh!")
            if values[0] == "raw":
                dlg.setText("No image found. Please check that the camera is on.")
            else:
                dlg.setText("No image found. Please check that the camera is on and that the processing script is processing.")
            dlg.exec_()
            return 

        # if settings didn't return None, continue to save location
        if values is not None:
            try:
                filedialog = QFileDialog(self)
                # set to select save file
                filedialog.setAcceptMode(QFileDialog.AcceptSave)
                # set default suffix to .fits
                filedialog.setDefaultSuffix("fits")
                # start dialog in /nfiudata directory
                filedialog.setDirectory("/nfiudata")
                # show that we're using .fits in filetype selection
                filedialog.setNameFilters(["FITS (*.fits)"])
                # if window was accepted
                if (filedialog.exec()):
                    # pull filename
                    filename = filedialog.selectedFiles()[0]
                    # save file 
                    img.writeto(filename, overwrite=True)
            except:
                dlg = QMessageBox()
                dlg.setWindowTitle("Uh oh!")
                dlg.setText("There was a problem saving the image.")
                dlg.exec_()
                return

    class Save_block_popup(QDialog):
        """A class to give a pop-up with options for saving a
            fits block
        """

        def __init__(self, *args, **kwargs):

            # run super constructor
            super().__init__(*args, **kwargs)

            # make a one-off timer to setup widget
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.setup)
            self.timer.start(10)

        def setup(self):
            """A method to setup this window"""

            uic.loadUi("{}/block_save.ui".format(resource_path), self)

            self.proc_im.setChecked(True)

            # make raw and processed images mutually exclusive
            self.proc_im.toggled.connect(lambda on : self.act_on_toggle(on, self.proc_im, self.raw_im))
            self.raw_im.toggled.connect(lambda on : self.act_on_toggle(on, self.raw_im, self.proc_im))

            # have selecting header at end/at start collapse count fields
            self.header_dropdown.currentIndexChanged.connect(self.act_dropdown)

            # hide fields at start
            self.header_cnt.hide()
            self.header_cnt_lbl.hide() 

            # set title
            self.setWindowTitle("Save block")

            self.resize(self.minimumSizeHint())

        def act_on_toggle(self, on:bool, this:QCheckBox, other:QCheckBox):
            """A method to act on toggle for raw/processed choice"""

            # if toggled on, turn other checkbox off
            if on: other.setChecked(False)
            # only allow toggle off if other checkbox is on
            else:
                if not other.isChecked(): this.setChecked(True)

        def act_dropdown(self):
            """A method to hide/show header cnt field for relevant dropdown
                selection
            """

            # if on save every x images, show fields
            if self.header_dropdown.currentIndex() == 1:
                self.header_cnt.show()
                self.header_cnt_lbl.show()
            else:
                self.header_cnt.hide()
                self.header_cnt_lbl.hide()
                self.resize(self.minimumSizeHint())

        def getResults(self):
            """Method to get results of the settings"""

            if self.exec_() == QDialog.Accepted:
                # get all values
                which = "vis" if self.proc_im.isChecked() else "raw"
                hdr_cnt = 0 if self.header_dropdown.currentIndex() == 0 else self.header_cnt.value()
                img_cnt = self.img_cnt.value()
                return which, hdr_cnt, img_cnt
            else:
                return None

class Raw_im_chk(QCheckBox):
    """A class to control the raw image view checkbox"""

    def __init__(self, *args, **kwargs):
        
        # run super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self, refresh_rate:int=500):
        """Method to setup this checkbox"""

        self.refresh_rate = refresh_rate

        self.imv = self.parent().image

        self.subtr_frame = self.parent().interfaces.findChild(QFrame, "subtraction_frame")
        self.scl_frame = self.parent().interfaces.findChild(QFrame, "scl_frame")
        self.smooth_frame = self.parent().interfaces.findChild(QFrame, "smooth_frame")

        self.toggled.connect(self.toggle_raw)

    def toggle_raw(self, toggled):
        """Method to act on checkbox toggle"""

        if toggled:
            self.subtr_frame.setEnabled(False)
            self.scl_frame.setEnabled(False)
            self.smooth_frame.setEnabled(False)
            self.imv.Img_shm = self.imv.raw_im
        else:
            self.subtr_frame.setEnabled(True)
            self.scl_frame.setEnabled(True)
            self.smooth_frame.setEnabled(True) 
            self.imv.Img_shm = self.imv.proc_im

class FPS(QLineEdit):
    """A class to control the FPS of the tracking camera
        (meant to be used in lab view only)
    """

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # if we're not in lab config
        if self.parent() is None: return

        # get tracking camera cmds library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.tc = self.p.proc.tc

        # set text validator
        self.setValidator(QDoubleValidator())

        # get shm fname    
        if type(self.tc.FPS_D) is str:
            nm = self.tc.FPS_D
        else: nm = self.tc.FPS_D.fname
        # try to connect to existing shm watcher
        try: self.parent().watch_widgs[nm].do_update.connect(self.update_txt)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_txt)
        try: self.update_txt(self.tc.FPS_D.get_data())
        except: pass

    def update_txt(self, data):
        """A method to write new value to text field"""

        try: self.setText(str(data[0]))
        except: self.setText("---")

    def focusOutEvent(self, *args, **kwargs):
        """A method to send new NDR on focus loss"""

        # try to set field
        try:
            if self.text() != "": 
                self.tc.set_fps(float(self.text()))
            else:
                self.setText(str(self.tc.get_fps()))
        except: pass

        super().focusOutEvent(*args, **kwargs)

class Tint(QLineEdit):
    """A class to control the Tint of the tracking camera
        (meant to be used in lab view only)
    """

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # if we're not in lab config
        if self.parent() is None: return

        # get tracking camera cmds library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.tc = self.p.proc.tc

        # set text validator
        self.setValidator(QDoubleValidator())

        # get shm fname    
        if type(self.tc.Exp_D) is str:
            nm = self.tc.Exp_D
        else: nm = self.tc.Exp_D.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_txt)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_txt)

        try: self.update_txt(self.tc.Exp_D.get_data())
        except: pass

    def update_txt(self, data):
        """A method to write new value to text field"""

        try: self.setText(str(1000*data[0]))
        except: self.setText("---")

    def focusOutEvent(self, *args, **kwargs):
        """A method to send new NDR on focus loss"""

        # try to set tint
        try: 
            if self.text() != "":
                self.tc.set_tint(float(self.text())/1000)
            else:
                self.setText(str(self.tc.get_tint()*1000))
        except: pass

        super().focusOutEvent(*args, **kwargs)

class NDR(QLineEdit):
    """A class to control the NDRs of the tracking camera
        (meant to be used in lab view only)
    """

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # if we're not in lab config
        if self.parent() is None: return

        # get tracking camera cmds library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.tc = self.p.proc.tc

        # set text validator
        self.setValidator(QIntValidator())

        # get shm fname    
        if type(self.tc.NDR_D) is str:
            nm = self.tc.NDR_D
        else: nm = self.tc.NDR_D.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_txt)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_txt)

        try: self.update_txt(self.tc.NDR_D.get_data())
        except: pass

    def update_txt(self, data):
        """A method to write new value to text field"""

        try: self.setText(str(data[0]))
        except: self.setText("---")

    def focusOutEvent(self, *args, **kwargs):
        """A method to send new NDR on focus loss"""

        # try to set field
        try:
            if self.text() != "":
                self.tc.set_ndr(float(self.text()))
            else:
                self.setText(str(self.tc.get_ndr()))
        except: pass

        super().focusOutEvent(*args, **kwargs)

##############################

####### Processing Tab #######

class Bias_chk(QCheckBox):
    """A checkbox to turn on/off bias subtraction"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera process library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        # connect self to use_minus_bias function
        self.toggled.connect(self.proc.use_minus_bias)

        # get shm fname    
        if type(self.proc.Vis_Stat) is str:
            nm = self.proc.Vis_Stat
        else: nm = self.proc.Vis_Stat.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_bx)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_bx)

        try: self.update_bx(self.proc.Vis_Stat.get_data())
        except: pass

    def update_bx(self, data):
        """A method to write new value to text field"""

        try: 
            # only check checked state if it needs to be
            check = bool(data[0] & 8)
            if not check == self.isChecked(): self.setChecked(check)
        except: pass

class Bkgrd_chk(QCheckBox):
    """A checkbox to turn on/off background subtraction"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera process library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        # connect self to use_minus_bias function
        self.toggled.connect(self.proc.use_minus_bkgrd)

        # get shm fname    
        if type(self.proc.Vis_Stat) is str:
            nm = self.proc.Vis_Stat
        else: nm = self.proc.Vis_Stat.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_bx)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_bx)

        try: self.update_bx(self.proc.Vis_Stat.get_data())
        except: pass

    def update_bx(self, data):
        """A method to write new value to text field"""

        try: 
            # only check checked state if it needs to be
            check = bool(data[0] & 16)
            if not check == self.isChecked(): self.setChecked(check)
        except: pass

class Bkgrd_save(QPushButton):
    """A class to save the currently loaded background"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera processing library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""
        
        # get how many images to average
        i, cont = QInputDialog.getInt(self.p, "Save Background","Images to average:", min=1)

        # if dialog wasn't canceled,
        if cont:
            # get images and average
            block = self.proc.grab_n(i, which="raw")
            img = np.mean([im.data for im in block], 0)
            # we use topmost widget as parent to avoid inherited stylesheet
            filedialog = QFileDialog(self.p)
            # set to select save file
            filedialog.setAcceptMode(QFileDialog.AcceptSave)
            # set default suffix to .fits
            filedialog.setDefaultSuffix("fits")
            # start dialog in /nfiudata directory
            filedialog.setDirectory("/nfiudata")
            # show that we're using .fits in filetype selection
            filedialog.setNameFilters(["FITS (*.fits)"])
            # if window was accepted
            if (filedialog.exec()):
                # pull filename
                filename = filedialog.selectedFiles()[0]
                try:
                    fits.PrimaryHDU(data=img, header=block[0].header).writeto(filename, overwrite=True)
                except:
                    dlg = QMessageBox()
                    dlg.setWindowTitle("Uh oh!")
                    dlg.setText("There was a problem saving the image.")
                    dlg.exec_()
                    return

                # load new frame as reference
                self.proc.load_bkgrd(filename)

class Bkgrd_load(QPushButton):
    """A class to load a background from from a .npy file"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera processing library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""

        # we use topmost widget as parent to avoid inherited stylesheet
        filedialog = QFileDialog(self.p)
        # set to select save file
        filedialog.setAcceptMode(QFileDialog.AcceptOpen)
        # set default suffix to .fits
        filedialog.setDefaultSuffix("fits")
        # start dialog in /nfiudata directory
        filedialog.setDirectory("/nfiudata")
        # show that we're using .fits in filetype selection
        filedialog.setNameFilters(["FITS (*.fits)"])
        # if window was accepted
        if (filedialog.exec()):
            # pull filename
            filename = filedialog.selectedFiles()[0]
            # load file into background shm
            try:
                self.proc.load_bkgrd(filename)
            except:
               dlg = QMessageBox()
               dlg.setWindowTitle("Uh oh!")
               dlg.setText("There was a problem loading the image.")
               dlg.exec_() 

class Ref_chk(QCheckBox):
    """A checkbox to turn on/off reference subtraction"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera process library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        # connect self to use_minus_bias function
        self.toggled.connect(self.proc.use_minus_ref)

        # get shm fname    
        if type(self.proc.Vis_Stat) is str:
            nm = self.proc.Vis_Stat
        else: nm = self.proc.Vis_Stat.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_bx)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_bx)

        try: self.update_bx(self.proc.Vis_Stat.get_data())
        except: pass

    def update_bx(self, data):
        """A method to write new value to text field"""

        try: 
            # only check checked state if it needs to be
            check = bool(data[0] & 32)
            if not check == self.isChecked(): self.setChecked(check)
        except: pass

class Ref_save(QPushButton):
    """A class to save the currently loaded background"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera processing library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""

        # get how many images to average
        i, cont = QInputDialog.getInt(self.p, "Save Reference","Images to average:", min=1)

        # if dialog wasn't canceled,
        if cont:
            # get images and average
            block = self.proc.grab_n(i, which="raw")
            img = np.mean([im.data for im in block], 0)
            # we use topmost widget as parent to avoid inherited stylesheet
            filedialog = QFileDialog(self.p)
            # set to select save file
            filedialog.setAcceptMode(QFileDialog.AcceptSave)
            # set default suffix to .fits
            filedialog.setDefaultSuffix("fits")
            # start dialog in /nfiudata directory
            filedialog.setDirectory("/nfiudata")
            # show that we're using .fits in filetype selection
            filedialog.setNameFilters(["FITS (*.fits)"])
            # if window was accepted
            if (filedialog.exec()):
                # pull filename
                filename = filedialog.selectedFiles()[0]
                try:
                    fits.PrimaryHDU(data=img, header=block[0].header).writeto(filename, overwrite=True)
                except:
                    dlg = QMessageBox()
                    dlg.setWindowTitle("Uh oh!")
                    dlg.setText("There was a problem saving the image.")
                    dlg.exec_()
                    return

                # load new frame as reference
                self.proc.load_ref(filename)

class Ref_load(QPushButton):
    """A class to load a background from from a .npy file"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera processing library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        self.clicked.connect(self.on_click)

    def on_click(self):
        """A method to run when this button is clicked"""

        # we use topmost widget as parent to avoid inherited stylesheet
        filedialog = QFileDialog(self.p)
        # set to select save file
        filedialog.setAcceptMode(QFileDialog.AcceptOpen)
        # set default suffix to .fits
        filedialog.setDefaultSuffix("fits")
        # start dialog in /nfiudata directory
        filedialog.setDirectory("/nfiudata")
        # show that we're using .fits in filetype selection
        filedialog.setNameFilters(["FITS (*.fits)"])
        # if window was accepted
        if (filedialog.exec()):
            # pull filename
            filename = filedialog.selectedFiles()[0]
            # load file into background shm
            try:
                self.proc.load_ref(filename)
            except:
               dlg = QMessageBox()
               dlg.setWindowTitle("Uh oh!")
               dlg.setText("There was a problem loading the image.")
               dlg.exec_() 

class Med_filt_chk(QCheckBox):
    """A checkbox to turn on/off median filter"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera process library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        # connect self to use_minus_bias function
        self.toggled.connect(self.proc.use_medfilt)

        # get shm fname    
        if type(self.proc.Vis_Stat) is str:
            nm = self.proc.Vis_Stat
        else: nm = self.proc.Vis_Stat.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_bx)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_bx)

        try: self.update_bx(self.proc.Vis_Stat.get_data())
        except: pass

    def update_bx(self, data):
        """A method to write new value to text field"""

        try: 
            # only check checked state if it needs to be
            check = bool(data[0] & 4)
            if not check == self.isChecked(): self.setChecked(check)
        except: pass

class Log_chk(QCheckBox):
    """A checkbox to turn on/off log scale"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera process library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        # connect self to use_minus_bias function
        self.toggled.connect(self.proc.use_log_scale)

        # get shm fname    
        if type(self.proc.Vis_Scale) is str:
            nm = self.proc.Vis_Scale
        else: nm = self.proc.Vis_Scale.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_bx)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_bx)

        try: self.update_bx(self.proc.Vis_Scale.get_data())
        except: pass

    def update_bx(self, data):
        """A method to write new value to text field"""

        try: 
            # only check checked state if it needs to be
            check = bool(data[0] == 1)
            if not check == self.isChecked(): self.setChecked(check)
        except: pass

class Sqrt_chk(QCheckBox):
    """A checkbox to turn on/off square root scale"""

    def __init__(self, *args, **kwargs):

        # call super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup this widget"""

        # get tracking camera process library
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.proc = self.p.proc

        # connect self to use_minus_bias function
        self.toggled.connect(self.proc.use_sqrt_scale)

       # get shm fname    
        if type(self.proc.Vis_Scale) is str:
            nm = self.proc.Vis_Scale
        else: nm = self.proc.Vis_Scale.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_bx)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_bx)
            
        try: self.update_bx(self.proc.Vis_Scale.get_data())
        except: pass

    def update_bx(self, data):
        """A method to write new value to text field"""

        try: 
            # only check checked state if it needs to be
            check = bool(data[0] == 2)
            if not check == self.isChecked(): self.setChecked(check)
        except: pass

class Scale_rng_input(QLineEdit):
    """A QLineEdit that reverts text if focus is lost with intermediate input"""

    def __init__(self, *args, refresh_rate:int = 500, **kwargs):

        super().__init__(*args, **kwargs)

        # field to hold last valid input
        self.last_valid = ""
        # field to hold refresh rate
        self.refresh_rate = refresh_rate

    def setup(self, role:str):
        """A method to setup the line edit
        
        Args:
            role = 'min' or 'max' depending on which range box this is
        """

        self.imv = self.parent().parent().top_lv.image

        self.role = role
        if self.role == "min":
            # a lambda function to check that value is less than max
            self.check = lambda x : x <= self.imv.max 
            # a lambda function to get current min value
            self.val   = lambda : self.imv.min
            # function to set a value (None to turn off)
            self.set   = self.set_min 
        elif self.role == "max":
            # a lambda function to check that value is greater than max
            self.check = lambda x : x >= self.imv.min
            # a lambda function to get current max value
            self.val   = lambda : self.imv.max
            # function to set a value (None to turn off)
            self.set   = self.set_max
        else:
            raise ValueError("Only 'min' and 'max' roles are valid")
        try: self.last_valid = self.val()
        except: self.last_valid = "---"
        
        self.setValidator(Scale_rng_input.rng_validator(le = self))

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def set_max(self, val):
        self.imv.max = val

    def set_min(self, val):
        self.imv.min = val

    def update(self):
        """A method to update the current min and max value if a custom value
            isn't requested"""

        # if we have focus, don't update
        if self.hasFocus(): return

        try:
            self.setText(str(self.val()))
            self.last_valid = self.val()        
        except:
            self.setText("---")

    def focusOutEvent(self, QFocusEvent):
        """Override to revert text if it is in 'Intermediate' state"""

        _state, _, _ = self.validator().validate(self.text(), self.pos())
        if _state == QValidator.Intermediate: self.setText(str(self.last_valid))
        elif _state == QValidator.Acceptable: self.last_valid = self.text()

        super().focusOutEvent(QFocusEvent)

    class rng_validator(QValidator):
        """A validator to validate the min value for the log scale"""

        def __init__(self, *args, le, **kwargs):
            """Stores the QGroubBox this belongs to

            Args:
                le = the lineedit that this validator is to validate
            """

            super().__init__(*args, **kwargs)

            self.p_le = le

        def validate(self, text:str, pos:str):
            """sets the min value in the log_scale parent of this validator"""

            # blank text is not valid, but we want to allow users to clear text box
            if text == "": return QValidator.Intermediate, text, pos

            # default to invalid
            _state = QValidator.Invalid
            try: 
                # check if text can be cast as an int
                num = int(text)
                # intermediate will be rejected on focus loss
                #   we want intermediate for max so you can clear number and then input
                #   we don't want it for min so you shouldn't be typing a number that's too large
                if self.p_le.role == 'max': _state = QValidator.Intermediate
            except: return _state, text, pos

            if self.p_le.check(num):
                _state = QValidator.Acceptable
                if self.p_le.isEnabled(): self.p_le.set(num)
                self.p_le.last_valid = num

            return _state, text, pos

class Scale_rng_chk_box(QCheckBox):
    """A class to handle the min/max scale range checkboxes"""

    def __init__(self, *args, **kwargs):
        """Constructor for scale rng chk box component"""

        # run super constructor
        super().__init__(*args, **kwargs)

    def setup(self, my_scale):
        """A method to set up the scale checkboxes
        
        Args:
            my_scale   = the method to turn the currect field on/off
        """

        self.my_scale = my_scale
        self.toggled.connect(self.act)

    def act(self, toggled:bool):
        """A method that turns on/off the relevant scale and, if turning
            on, turns off any other scales"""

        try: self.my_scale(toggled)
        except: pass

class Gradient(QWidget):
    """A class to make a selectable gradient"""

    def __init__(self, *args, **kwargs):
        """Constructor"""

        # call super constructor
        super().__init__(*args, **kwargs)

        # start a timer to run setup after 10 ms
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """A method to setup the gradient"""

        self.top_lv = self.parent().parent().parent().parent()

        self.imv = self.top_lv.image

        # load widget ui
        uic.loadUi("{}/gradient_sel.ui".format(resource_path), self)

        # setup checkboxes
        self.min_chk.setup(self.min_lamb)
        self.max_chk.setup(self.max_lamb)
        try:
            if self.top_lv.proc.PRng.get_data()[0]: self.min_chk.setChecked(True)
            else: self.min_chk.setChecked(False)
        except: self.min_chk.setChecked(False)
        try:
            if self.top_lv.proc.PRng.get_data()[2]: self.max_chk.setChecked(True)
            else: self.max_chk.setChecked(False)
        except: self.max_chk.setChecked(False)

        # setup inputs
        self.min_val.setup("min")
        self.max_val.setup("max")

        # gradient type will be in accessible description
        grad = self.toolTip()

        grad = Gradients[grad]

        # format stylesheet of gradient (Gradient is upside down, so flip it)
        bkgrd = "background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2: 1"
        for tick in grad["ticks"]:
            bkgrd += ", stop:{} rgba{}".format(1-tick[0], str(tick[1]))
        bkgrd = bkgrd + ");"
        bkgrd = """
        QPushButton{{
            {0}
            border-style: none;
        }}
        QPushButton:checked {{
            {0}
            border-style: none;
        }}""".format(bkgrd)
        self.grad_btn.setStyleSheet(self.styleSheet()+bkgrd)

        # format lookup table (flip colormaps so darker colors are 0)
        self.lup = pg.ColorMap([c[0] for c in grad['ticks']],
                           [c[1] for c in grad['ticks']],
                            mode = grad['mode'])
        self.lup = self.lup.getLookupTable()

        # connect grad_btn to interact with other grad buttons and with image
        self.grad_btn.toggled.connect(self.act)

        self.grad_btn.setChecked(True)
        if self.toolTip() == "grey":
            # if this is greyscale, save it in the image widget
            self.imv.no_lup = self
            self.imv.grad_widg = self

    def min_lamb(self, toggled): self.top_lv.image.automin = not toggled
    def max_lamb(self, toggled): self.top_lv.image.automax = not toggled

    def act(self, toggled_on:bool):
        """
        A method to act when a button is toggled

        if button is toggled on, will deactivate any currently active gradient and switch
            image's gradient to this one
        if button is toggled off, will set image's gradient to no_gradient

        Args:
            toggled_on = True if toggled on, False if toggled off
        """

        if toggled_on:
            # store old gradient
            old_grad = self.imv.grad_widg
            # set image's gradient widget to self
            self.imv.grad_widg = self
            # set new lookup table (colormap)
            self.imv.img.setLookupTable(self.lup)

            if old_grad is not self and old_grad is not None:
                # disable current gradient
                old_grad.grad_btn.setChecked(False)
        elif not self.imv.grad_widg.grad_btn.isChecked():
            self.grad_btn.setChecked(True)

##############################

######## Tracking Tab ########

class Loc_Selection(QFrame):
    """A class to represent the QFrame holding PSF location information in the KPIC GUI"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setup_timer = QTimer(self)
        self.setup_timer.setSingleShot(True)
        self.setup_timer.timeout.connect(self.setup)
        self.setup_timer.start(10)

    def setup(self):
        # variable to store which index is the custom option
        self.custom_idx = 5

        # get all the parts we will be interacting with
        self.drop = self.findChild(QComboBox, "psf_loc_dropdown")
        self.x = self.findChild(QLineEdit, "psf_x_input")
        self.y = self.findChild(QLineEdit, "psf_y_input")
        self.submit = self.findChild(QPushButton, "psf_loc_btn")
        self.input_frame = self.findChild(QFrame, "psf_input_frame")

        if self.drop.currentIndex() != self.custom_idx:
            self.input_frame.hide()

        # connect method to monitor goal change
        self.drop.currentIndexChanged.connect(self.sel_chng)
        
    def sel_chng(self):
        """A method to handle when the goal selection drop down is changed"""

        # if option selected is "custom", show input fields
        if self.drop.currentIndex() == self.custom_idx:
            self.input_frame.show()
        # otherwise hide input fields
        else:
            self.input_frame.hide()

##############################

########## Mode Tab ##########

class View_Selection(QFrame):
    """A class to represent the QFrame holding viewing mode information in the KPIC GUI"""
    
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setup_timer = QTimer(self)
        self.setup_timer.setSingleShot(True)
        self.setup_timer.timeout.connect(self.setup)
        self.setup_timer.start(10)

    def setup(self):
        # get top level widget of GUI
        self.p = self.parent()
        while self.p.parent() is not None:
            self.p = self.p.parent()
        self.mc = self.p.mc

        # get shm fname    
        if type(self.mc.Pos_D) is str:
            nm = self.mc.Pos_D
        else: nm = self.mc.Pos_D.fname
        # try to connect to existing shm watcher
        try: self.p.watch_widgs[nm].do_update.connect(self.update_pos)
        # if none exists yet, make a new one
        except KeyError:
            self.p.watch_widgs[nm]=Shm_Watcher(parent = self.p)
            self.p.watch_widgs[nm].setup(nm)
            self.p.watch_widgs[nm].do_update.connect(self.update_pos)

        # variable to store which index is the custom option
        self.custom_idx = 2

        # get all the parts we will be interacting with
        self.drop = self.findChild(QComboBox, "view_mode_dropdown")
        self.val = self.findChild(QLineEdit, "custom_pos")
        self.val.setValidator(QDoubleValidator(bottom=0.0, top=27.0))
        self.submit = self.findChild(QPushButton, "view_mode_custom_btn")
        self.input_frame = self.findChild(QFrame, "view_mode_custom_frame")

        if self.drop.currentIndex() != self.custom_idx:
            self.input_frame.hide()

        # connect button to submitting new position
        self.submit.clicked.connect(self.set_pos)

        # update current selection
        try: self.update_pos(self.mc.Pos_D.get_data())
        except: self.update_pos(["---"])

        # connect method to monitor goal change
        self.drop.currentIndexChanged.connect(self.sel_chng)
        
    def sel_chng(self):
        """A method to handle when the goal selection drop down is changed"""

        # if option selected is "pupil", go to pupil plane
        if self.drop.currentIndex() == 0:
            try: self.mc.set_pos("pupil")
            except:
                try: self.update_pos(self.mc.Pos_D.get_data())
                except: self.update_pos("---")
        # if option selected is "focal", go to focal plane
        elif self.drop.currentIndex() == 1:
            try: self.mc.set_pos("focal")
            except:
                try: self.update_pos(self.mc.Pos_D.get_data())
                except: self.update_pos("---")
        # if option selected is "custom", show input fields
        elif self.drop.currentIndex() == self.custom_idx:
            self.input_frame.show()
        # otherwise hide input fields
        else:
            self.input_frame.hide()

    def set_pos(self, *ignored):
        """A method to set a custom position"""

        try: self.mc.set_pos(float(self.val.text()))
        except:
            try: self.update_pos(self.mc.Pos_D.get_data())
            except: self.update_pos("---")

    def update_pos(self, data):
        """A method to update dropdown selection when stage is moved"""

        # get the current position by name
        nm_pos = self.mc.get_named_pos()
        if nm_pos.lower() == "pupil":
            idx = 0
        elif nm_pos.lower() == "focal":
            idx = 1
        # if not any of the above, it's in a custom position
        else:
            idx = self.custom_idx

        # set new index if not the current one
        if self.drop.currentIndex() != idx:
            self.drop.setCurrentIndex(idx)

        # update text field
        try: self.val.setText(str(data[0]))
        except: self.val.setText("---")

        # if text field should be hidden, hide it
        if self.drop.currentIndex() != self.custom_idx:
            self.input_frame.hide()

##############################