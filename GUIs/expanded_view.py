# inherent python libraries
from configparser import ConfigParser
from time import sleep
import sys

# installs
from PyQt5.QtWidgets import QWidget, QComboBox
from PyQt5 import uic

# import Brief view so we don't need to repeat setting up left section
from brief_view import Brief
# night_view_widgets has all the widgets in the .ui
from night_view_widgets import *
# this is the KPIC logo
import resources.KPIC_logo_rc

# a widget to handle the expanded view
#   we extend the brief view so that any changes made there are reflected here
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

        # we load in all the QLabels that need to be updated
        self.elements = {}
        self._load_elements()

    def _load_elements(self):
        """A method to load the updatable elements from the .ui file
        
        We expand on the brief load elements in order to not have to repeat
        """
        
        ###### load brief pane ######
        Brief._load_elements(self)
        ###### load FIU setup elements ######
        self.elements["fiu_ttm_val"] = self.findChild(FIU_TTM_stat, "fiu_ttm_val")
        self.elements["fiu_ttm_x_val"] = self.findChild(FIU_TTM_x, "fiu_ttm_x_val")
        self.elements["fiu_ttm_y_val"] = self.findChild(FIU_TTM_y, "fiu_ttm_y_val")

    def update_vals(self):
        """A method that updates all the values in the GUI"""

        for elem in self.elements:
            if issubclass(type(elem), QWidget):
                self.elements[elem].update()

        self.update()