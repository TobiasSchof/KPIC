import os

from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit, QFrame, QComboBox, QGroupBox, QHBoxLayout, QCheckBox
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QPixmap, QPainter, QImage, QValidator, QIntValidator
from PyQt5 import uic
import numpy as np

# nfiuserver libraries
from KPIC_shmlib import Shm
import resources.no_img

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

class Img(QLabel):
    """A widget to display the image and maintain aspect ratio while changing size"""

    def __init__(self, *args, refresh_rate:int = 40, **kwargs):
        """Constructor
        
        Args:
            refresh_rate = the number of milliseconds to wait before refreshing widget
            """

        super().__init__(*args, **kwargs)

        # save copy of placeholder image for if img file is old
        #   or doesn't exist
        self.placeholder = None
        # save copy of unscaled image so that we can rescale GUI
        self.unscaled_img = None
        # save copy of scaled image
        self.scaled_img = None

        # store refresh rate
        self.refresh_rate = refresh_rate

        self.timer = QTimer()
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """Saves an unscaled image"""

        self.placeholder = QPixmap(":/placeholder/no_img.jpg")
        self.unscaled_img = self.placeholder
        self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)

        self.setPixmap(self.placeholder)

        self.Img = "/tmp/Track_Cam/PROCIMG.im.shm"

        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """Method to try to fetch a new image"""

        try:
            if type(self.Img) is str:
                self.Img = Shm(self.Img)

            img = self.Img.get_data()

            self.unscaled_img = QPixmap(QImage(img, self.Img.mtdata["size"][0],
                self.Img.mtdata["size"][1], QImage.Format_Grayscale16))
            self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)

            self.setPixmap(self.scaled_img)
        except:
            if type(self.Img) is not str and not os.path.exists(self.Img.fname):
                self.Img = self.Img.fname

            self.unscaled_img = self.placeholder
            self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)
            self.setPixmap(self.scaled_img)

        self.timer.start(self.refresh_rate)

    def minimumSizeHint(self):
        """Returns the size of the unscaled image as a minimum size"""

        try:
            return QSize(self.unscaled_img.width(), self.unscaled_img.height())
        except:
            return QSize(640, 512)

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

class log_lineedit(QLineEdit):
    """A QLineEdit that reverts text if focus is lost with intermediate input"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # field to hold last valid input
        self.last_valid = ""
        # field to hold current value
        self.val = None

    def setup(self):
        """A method to setup the line edit"""

        self.setValidator(log_lineedit.log_validator())

    def focusOutEvent(self, QFocusEvent):
        """Override to revert text if it is in 'Intermediate' state"""

        _state, _, _ = self.validator().validate(self.text(), self.pos())
        if _state == QValidator.Intermediate: self.setText(self.last_valid)
        elif _state == QValidator.Acceptable: self.last_valid = self.text()

        super().focusOutEvent(QFocusEvent)

    class log_validator(QValidator):
        """A validator to validate the min value for the log scale"""

        def __init__(self, *args, parent_scope, which, **kwargs):
            """Stores the QGroubBox this belongs to

            Args:
                parent_scope = the groupbox that this exists within
                which = one of 'min' or 'max'
            """

            super().__init__(*args, **kwargs)

            self.p_sc = parent_scope
            self.role = which

        def validate(self, text:str, pos:str):
            """sets the min value in the log_scale parent of this validator"""

            if text == "":
                self.p_sc.val = None
                return QValidator.Acceptable, text, pos

            _state = QValidator.Invalid
            try: 
                num = int(text)
                # intermediate will be rejected on focus loss
                if self.role == 'max': _state = QValidator.Intermediate
            except: return _state, text, pos

            if (self.role == 'min' and (self.p_sc.val is None or num < self.p_sc.val))\
                or (self.role == 'max' and (self.p_sc.val is None or num > self.p_sc.val)):

                _state = QValidator.Acceptable

                self.p_sc.val = num

            return _state, text, pos