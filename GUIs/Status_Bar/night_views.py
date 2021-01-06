# inherent python libraries
from configparser import ConfigParser
from time import sleep
import sys

# installs
from PyQt5.QtWidgets import QWidget, QComboBox, QFrame, QGridLayout
from PyQt5 import uic

# night_view_widgets has all the widgets in the .ui
from night_view_widgets import *
# this is the KPIC logo
import resources.KPIC_logo_rc

# a widget to handle the expanded view
class Expanded(QWidget):

    # constructor
    def __init__(self, resource_path):
        # first we call the super constructor
        super(Expanded, self).__init__()

        # then we load the layout from the .ui file
        uic.loadUi("{}/status_bar_night_expanded.ui".format(resource_path), self)

        # we want QComboBox fields accessible from elsewhere so we make separate variables for them
        self.view_val = self.findChild(QComboBox, "view_val")
        self.mode_val = self.findChild(QComboBox, "mode_val")

# a widget to handle the brief view
class Brief(QWidget):

    # constructor
    def __init__(self, resource_path):
        # first we call the super constructor
        super(Brief, self).__init__()

        # then we load the layout from the .ui file
        uic.loadUi("{}/status_bar_night_expanded.ui".format(resource_path), self)

        # remove vertical separating line from expanded view
        self.findChild(QFrame, "vline_mid").setParent(None)
        # remove right half from expanded view
        layout = self.findChild(QGridLayout, "right_col_layout")
        # to remove a layout, we have to set parent of each element in the layout to None
        for i in reversed(range(layout.count())): 
            widg = layout.itemAt(i).widget()
            # there are some empty cells in the layout so skip those
            if not widg is None:
                widg.setParent(None)

        # we want QComboBox fields accessible from elsewhere so we make separate variables for them
        self.view_val = self.findChild(QComboBox, "view_val")
        self.mode_val = self.findChild(QComboBox, "mode_val")
        # we want to set the current view box to brief
        self.view_val.setCurrentIndex(1)