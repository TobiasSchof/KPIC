from PyQt5.QtWidgets import QWidget, QComboBox
from PyQt5 import uic
from configparser import ConfigParser
from time import sleep
import sys

resources = "/Users/tobias/Documents/Git/KPIC/GUI/resources"

class Expanded(QWidget):
    def __init__(self):
        super(Expanded, self).__init__()
        uic.loadUi("{}/status_bar_night_expanded.ui".format(resources), self)
        self.view_val = self.findChild(QComboBox, "view_val")

class Brief(QWidget):
    def __init__(self):
        super(Brief, self).__init__()
        uic.loadUi("{}/status_bar_night_brief.ui".format(resources), self)
        self.view_val = self.findChild(QComboBox, "view_val")
        self.view_val.setCurrentIndex(1)