#!/usr/bin/env python

# inherent python libraries
from time import sleep
import sys

# installs
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QComboBox
from PyQt5 import uic

# custom widgets
from Viewer_Widgets import *

resource_path = "/Users/tobias/Documents/Git/KPIC/GUIs/Viewer/resources"

class Stack(QWidget):

    def __init__(self):
        """Constructor"""

        super().__init__()

        uic.loadUi("{}/Viewer.ui".format(resource_path), self)

        # setup widgets after elements are loaded
        self.findChild(Loc_Selection, "psf_loc_frame").setup()

        self.min_btn = self.findChild(QPushButton, "minimize_btn")
        self.min_btn.clicked.connect(self.btn_click)

        self.log_box = self.findChild(Log_Scale, "logscale_box")
        self.log_box.setup()

        self.ctrl_pnl = self.findChild(QFrame, "ctrl_frame")

        self.img_label = self.findChild(QLabel, "image")

        self.resize(self.minimumWidth(), self.minimumHeight())
        self.show()

        self.log = self.log_box.isChecked
        self.img_max = lambda : self.log_box.max
        self.img_min = lambda : self.log_box.min

        self.setWindowTitle("KPIC Display")
    
    def btn_click(self):
        """method that minimizes or maximizes the control panel"""

        # variable for storing new geometry
        width = self.geometry().width()

        if self.min_btn.isChecked():
            self.ctrl_pnl.show()
            self.min_btn.setText("<")
            width += self.ctrl_pnl.geometry().width()
        else:
            self.ctrl_pnl.hide()
            self.min_btn.setText(">")
            width -= self.ctrl_pnl.geometry().width()

        app.processEvents()
        self.resize(width, self.geometry().height())

app = QApplication(sys.argv)
widge = Stack()
sys.exit(app.exec_())