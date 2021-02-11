# standard libraries
from time import time
import os

# installs
from PyQt5.QtWidgets import QLineEdit, QFrame, QComboBox, QCheckBox, QWidget, QPushButton, QFileDialog, QDialog, QMessageBox
from PyQt5.QtCore import Qt, QTimer, QSize, QTemporaryDir, QFile 
from PyQt5.QtGui import QPixmap, QPainter, QImage, QValidator, QIntValidator, QDoubleValidator, QFont 
from PyQt5 import uic
from PIL import Image
from astropy.io import fits
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients
import pyqtgraph as pg
import numpy as np

# nfiuserver libraries
from KPIC_shmlib import Shm
import resources.images

resource_path = "/Transfer/Viewer/resources"

class Loc_Selection(QFrame):
    """A class to represent the QFrame holding PSF location information in the KPIC GUI"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

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

class Scale_chk_box(QCheckBox):
    """A widget to toggle a scale on the image"""

    def __init__(self, *args, **kwargs):
        """Constructor for scale chk box component"""

        # run super constructor
        super().__init__(*args, **kwargs)

    def setup(self, all_scales:list, my_scale):
        """A method to set up the scale checkboxes
        
        Args:
            all_scales = a list of all Scale_chk_boxes (including this one)
            my_scale   = the method to turn the correct scale on/off
        """

        # get sqrt scale checkbox
        self.chkboxes = all_scales[:]
        self.chkboxes.remove(self)

        self.my_scale = my_scale
        self.toggled.connect(self.act)

    def act(self, toggled:bool):
        """A method that turns on/off the relevant scale and, if turning
            on, turns off any other scales"""

        if toggled:
            for chkbox in self.chkboxes:
                chkbox.setChecked(False)
        self.my_scale(toggled)

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

    def setup(self, refresh_rate = 1000):
        """A method to setup this widget"""

        self.tc = self.parent().proc.tc

        self.setValidator(QIntValidator())

        # run update once
        self.update()

        # setup repeating timer to update value
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

    def update(self):
        """A method to keep field value correct"""

        # if we have focus (meaning someone is editing field),
        #   don't update
        if self.hasFocus(): return

        try: self.setText(str(self.tc.get_fps()))
        except: self.setText("---")

    def focusOutEvent(self, *args, **kwargs):
        """A method to send new FPS on focus loss"""

        # try to set tint
        try: self.tc.set_fps(int(self.text()))
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

    def setup(self, refresh_rate = 1000):
        """A method to setup this widget"""

        self.tc = self.parent().proc.tc

        self.setValidator(QDoubleValidator())

        # run update once
        self.update()

        # setup repeating timer to update value
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

    def update(self):
        """A method to keep field value correct"""

        # if we have focus (meaning someone is editing field),
        #   don't update
        if self.hasFocus(): return

        try: self.setText(str(self.tc.get_tint()*1000))
        except: self.setText("---")
    
    def focusOutEvent(self, *args, **kwargs):
        """A method to send new tint on focus loss"""

        # try to set tint
        try: self.tc.set_tint(float(self.text()) / 1000)
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

    def setup(self, refresh_rate = 1000):
        """A method to setup this widget"""

        self.tc = self.parent().proc.tc

        self.setValidator(QIntValidator())

        # run update once
        self.update()

        # setup repeating timer to update value
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

    def update(self):
        """A method to keep field value correct"""

        # if we have focus (meaning someone is editing field),
        #   don't update
        if self.hasFocus(): return

        try: self.setText(str(self.tc.get_ndr()))
        except: self.setText("---")

    def focusOutEvent(self, *args, **kwargs):
        """A method to send new NDR on focus loss"""

        # try to set tint
        try: self.tc.set_ndr(int(self.text()))
        except: pass

        super().focusOutEvent(*args, **kwargs)

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
            fileName, _ = QFileDialog.getSaveFileName(self,"Save raw frame","/nfiudata","All Files (*);;Python Files (*.py)")
            if fileName:
               img.writeto(fileName, overwrite=True)
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
            fileName, _ = QFileDialog.getSaveFileName(self,"Save raw frame","/nfiudata","All Files (*);;Python Files (*.py)")
            if fileName:
               img.writeto(fileName, overwrite=True)
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

        # if settings didn't return None, continue to save location
        if values is not None:
            try:
                fileName, _ = QFileDialog.getSaveFileName(self,"Save raw frame","/nfiudata","All Files (*);;Python Files (*.py)")
                # if fileName isn't empty, grab images
                if fileName:
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

                    # try writing fits to file
                    img.writeto(fileName, overwrite=True)
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
            self.parent().base_img_chk.setEnabled(False)
            self.subtr_frame.setEnabled(False)
            self.scl_frame.setEnabled(False)
            self.smooth_frame.setEnabled(False)
            self.imv.Img_shm = self.imv.raw_im
        else:
            self.parent().base_img_chk.setEnabled(True)
            self.subtr_frame.setEnabled(True)
            self.scl_frame.setEnabled(True)
            self.smooth_frame.setEnabled(True) 
            self.imv.Img_shm = self.imv.proc_im

class Base_use_chk(QCheckBox):
    """A class to monitor the use tracking checkbox"""

    def __init__(self, *args, **kwargs):

       # run super constructor
        super().__init__(*args, **kwargs)

        # make a one-off timer to setup widget
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)
 
    def setup(self, refresh_rate:int=500):
        """Method to setup this check box
        
        Args:
            refresh_rate = the polling rate in ms to update this widget
        """

        self.refresh_rate = refresh_rate

        f_subt = self.parent().interfaces.findChild(QFrame, "subtraction_frame") 
        self.bias_subt = f_subt.findChild(QCheckBox, "bias_sub")
        self.bkgrd = [f_subt.findChild(QCheckBox, "bkgrd_sub"), 
                      f_subt.findChild(QPushButton, "bkgrd_take"),
                      f_subt.findChild(QPushButton, "bkgrd_load"),
                      f_subt.findChild(QPushButton, "bkgrd_save")]

        self.medfilt = self.parent().interfaces.findChild(QFrame, "smooth_frame").findChild(QCheckBox, "med_filt")

        self.proc = self.parent().proc

        self.toggled.connect(self.act)

        self.setChecked(self.proc.is_using_base())
        if self.isChecked():
            self.bias_subt.setEnabled(False)
        else:
            self.bias_subt.setEnabled(True)

        # make a repeating timeout
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """A method to update this check box to make sure that it stays up to date"""

        checked = self.proc.is_using_base()

        if not (checked == self.isChecked()):
            self.toggle(checked)
        # if using base processing, check if anything has changed
        elif checked:
            base_mf = self.proc.is_medfilt(vis = False)

            # if base processing is already med filtering, but checkbox is enabled, disable
            if base_mf and self.medfilt.isEnabled():
                self.medfilt.setEnabled(False)
            # if base processing isn't using med filtering, but checkbox is disabled, enable
            elif not base_mf and not self.medfilt.isEnabled():
                self.medfilt.setEnabled(True)

            # if base processing is subtracting calib image, disable bkgrd subtraction
            calib_sub = self.proc.is_minus_calib()

            if calib_sub:
                for widg in self.bkgrd:
                    if widg.isEnabled(): widg.setEnabled(False)
            else:
                for widg in self.bkgrd:
                    if not widg.isEnabled(): widg.setEnabled(True)

    def act(self, toggled):
        """A method to act when this checkbox is toggled"""

        # base processing on so disable bias subtraction,
        #   disable bkgrd subtraction if calib being used
        if toggled:
            self.proc.use_base(True)
            if self.bias_subt.isEnabled(): self.bias_subt.setEnabled(False)
            if self.bkgrd[0].isEnabled() and self.proc.is_minus_calib(): 
                for widg in self.bkgrd:
                    widg.setEnabled(False)
        # enable anything that's disabled
        else:
            self.proc.use_base(False)
            for widg in [self.bias_subt, self.medfilt]+self.bkgrd:
                if not widg.isEnabled(): widg.setEnabled(True)

