import os

from PyQt5.QtWidgets import QLineEdit, QFrame, QComboBox, QCheckBox, QWidget, QPushButton
from PyQt5.QtCore import Qt, QTimer, QSize, QTemporaryDir, QFile 
from PyQt5.QtGui import QPixmap, QPainter, QImage, QValidator, QIntValidator 
from PyQt5 import uic
from PIL import Image
from time import time
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients
import pyqtgraph as pg
import numpy as np

# nfiuserver libraries
from KPIC_shmlib import Shm
import resources.no_img

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
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

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

        # connect to shm
        self.Img_shm = "/tmp/Track_Cam/PROCIMG.im.shm"

        # start a repeating timer to trigger update
        self.timer.timeout.connect(self.update)
        self.timer.timeout.disconnect(self.setup)
        self.timer.setSingleShot(False)
        self.timer.start(self.refresh_rate)

    def update(self):
        """Method to try to fetch a new image"""

        try:
            if type(self.Img_shm) is str:
                self.Img_shm = Shm(self.Img_shm)

            self.Img_shm.read_meta_data()
            # if image is at least two minutes old, use placeholder
            if time() - self.Img_shm.mtdata["atime_sec"] > 120: assert 0 == 1

            self.img.setImage(np.rot90(self.Img_shm.get_data(reform=True)))

        except:
            if type(self.Img_shm) is not str and not os.path.exists(self.Img_shm.fname):
                self.Img_shm = self.Img_shm.fname

            self.img.setImage(self.placeholder)

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

    def setup(self, proc, role:str):
        """A method to setup the line edit
        
        Args:
            proc = an instance of TC_process to get/set min/max values
            role = 'min' or 'max' depending on which range box this is
        """

        self.role = role
        if self.role == "min":
            # a lambda function to check that value is less than max
            self.check = lambda x : x <= proc.get_range()[1]
            # a lambda function to get current min value
            self.val   = lambda : proc.get_range()[0]
            # a lambda function to set the min value (None to turn off)
            self.set   = lambda x : proc.set_range(min=x)
        elif self.role == "max":
            # a lambda function to check that value is greater than max
            self.check = lambda x : x >= proc.get_range()[1]
            # a lambda function to get current max value
            self.val   = lambda : proc.get_range()[1]
            # a lambda function to set the max value (None to turn off)
            self.set   = lambda x : proc.set_range(max=x)
        else:
            raise ValueError("Only 'min' and 'max' roles are valid")
        try: self.last_valid = self.val()
        except: self.last_valid = "---"
        
        self.setValidator(Scale_rng_input.rng_validator(le = self))

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """A method to update the current min and max value if a custom value
            isn't requested"""

        try:
            if not self.isEnabled():
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
        self.min_chk.setup(lambda b : self.top_lv.proc.set_range(min=0 if b else None))
        self.max_chk.setup(lambda b : self.top_lv.proc.set_range(max=65536 if b else None))
        if self.top_lv.proc.PRng.get_data()[0]: self.min_chk.setChecked(True)
        else: self.min_chk.setChecked(False)
        if self.top_lv.proc.PRng.get_data()[2]: self.max_chk.setChecked(True)
        else: self.max_chk.setChecked(False)

        # setup inputs
        self.min_val.setup(self.top_lv.proc, "min")
        self.max_val.setup(self.top_lv.proc, "max")

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