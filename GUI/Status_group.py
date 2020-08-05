"""A class to wrap multiple modules' statuses into a single button"""

from PyQt5.QtWidgets import QPushButton, QWidget, QVBoxLayout
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import QSize

class Mod_Wrap(QPushButton):

    def __init__(self, text:str, color:QColor, *args, **kw_args):
        """Constructor"""

        # call super class for QWidget
        super(Mod_Wrap, self).__init__(text, *args, **kw_args)

        # variable to store modules that appear in expanded view
        self.modules = []

        # variable to store text and color of button
        self.text = text
        self.color = color

        # make this button checkable (acts like a switch)
        self.setCheckable(True)

        # a boolean flag to represent whether this group's modules are contained in a layout
        self.showing = False

    def _color(self):
        """Set's this button's color

        Sets the color to whatever is currently stored in self.color
        """

        self.setStyleSheet("background-color: {}".format(self.color.name()))


    def con_click(self, func):
        """Connects the given function to this widget's button

        Args:
            func = the function to be called when this button is pressed
        """

        self.clicked.connect(func)

    def hide_modules(self) -> list:
        """A method to remove all this group's modules by setting their parents to this"""

        for mod in self.modules:
            mod.hide()
            mod.setParent(self)

        self.showing = False

    def show_modules(self, layout, col):
        """Adds this group's modules to the given layout in the given column

        will place modules starting at row 2

        Args:
            layout = a QGridLayout to place the modules in
            col    = the column to put the modules in
        """

        for row, mod in enumerate(self.modules):
            layout.addWidget(mod, row + 2, col, 1, 1)
            mod.show()

        self.showing = True