#!/usr/bin/env python

# inherent python libraries
from time import sleep
import sys

# installs
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QTabWidget
from PyQt5 import uic

# nfiuserver libraries
from Viewer_Widgets import *
from Track_Cam_process import TC_process

resource_path = "/Transfer/Viewer/resources"

class Stack(QWidget):

    def __init__(self):
        """Constructor"""

        super().__init__()

        # instantiate TC_process class
        self.proc = TC_process()

        uic.loadUi("{}/Viewer.ui".format(resource_path), self)

        # setup widgets after elements are loaded
        self.interfaces = self.findChild(QTabWidget, "interfaces")

        # setup widgets in Tracking tab
        self.interfaces.findChild(Loc_Selection, "psf_loc_frame").setup()

        # setup widgets in Processing tab
        log_scl = self.interfaces.findChild(Scale_chk_box, "log_scl")
        sqrt_scl = self.interfaces.findChild(Scale_chk_box, "sqrt_scl")

        scls = [log_scl, sqrt_scl]
        log_scl.setup(scls, self.proc.use_log_scale)
        sqrt_scl.setup(scls, self.proc.use_sqrt_scale)

        # setup minimize interface button
        self.min_btn = self.findChild(QPushButton, "minimize_btn")
        self.min_btn.clicked.connect(self.btn_click)

        #self.log_box = self.interfaces.findChild(Log_Scale, "logscale_box")
        #self.log_box.setup()

        self.img_label = self.findChild(QLabel, "image")

        self.resize(self.minimumWidth(), self.minimumHeight())
        self.show()

        #self.log = self.log_box.isChecked
        #self.img_max = lambda : self.log_box.max
        #self.img_min = lambda : self.log_box.min

        self.setWindowTitle("KPIC Display")
    
    def btn_click(self):
        """method that minimizes or maximizes the control panel"""

        # variable for storing new geometry
        width = self.geometry().width()

        if self.min_btn.isChecked():
            self.min_btn.setText("<")
            width += self.interfaces.geometry().width()
        else:
            self.min_btn.setText(">")
            width -= self.interfaces.geometry().width()

        app.processEvents()
        self.resize(width, self.geometry().height())

app = QApplication(sys.argv)
widge = Stack()
sys.exit(app.exec_())