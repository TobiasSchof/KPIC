#!/usr/bin/env kpython3

# inherent python libraries
from configparser import ConfigParser
from time import sleep
import sys

# installs
from PyQt5.QtWidgets import QApplication, QStackedWidget, QSizePolicy
from PyQt5.QtCore import QTimer

# import different views for status bar
from night_views import Expanded, Brief
# night_view_widgets holds all the widgets for the night views
from night_view_widgets import *

class Stack(QStackedWidget):

    def __init__(self, views:list):
        super(Stack, self).__init__()

        for view in views:
            view.view_val.currentIndexChanged.connect(self.set_view)
            self.addWidget(view)

        self.show()

        self.setWindowTitle("KPIC Status Bar")

        self.set_view()

    def set_view(self):
        # ignore size policy of the view we are no longer using
        self.currentWidget().setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # change view and view selection in new view
        self.setCurrentIndex(self.currentWidget().view_val.currentIndex())
        self.currentWidget().view_val.setCurrentIndex(self.currentIndex())

        # use size policy of the new view
        self.currentWidget().setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        # set size to sizehint of current view
        self.resize(self.currentWidget().sizeHint())

    def sizeHint(self):
        return self.currentWidget().sizeHint()

    def minimumSizeHint(self):
        return self.currentWidget().minimumSizeHint()

# path to the resource files (.ui, images, etc.)
resources = "/home/nfiudev/dev/Status_Bar/resources"

app = QApplication(sys.argv)
views = [Expanded(resources), Brief(resources)]
stack = Stack(views)
# in order to resize to current widget, we set stack's size policy to maximum (which has shrink flag)
stack.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
sys.exit(app.exec_())