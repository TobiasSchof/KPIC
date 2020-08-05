from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

from Status_group import Mod_Wrap

class View(Mod_Wrap):

    def __init__(self, *args, **kw_args):
        """Constructor"""

        super(View, self).__init__("Viewing", QColor("red").lighter(), *args, **kw_args)

        self._color()

        self.modules = [
            QLabel("Conex"),
            QLabel("CRED2 led"),
            QLabel("CRED2 fan"),
            QLabel("CRED2 temp")
        ]

        self.modules[0].setToolTip("Conex is moving (light leak)")
        self.modules[1].setToolTip("CRED2 led is off")
        self.modules[2].setToolTip("CRED2 fan is off")
        self.modules[3].setToolTip("CRED2 is at -40C")

        for mod in self.modules:
            mod.setAlignment(Qt.AlignCenter)
            mod.setAutoFillBackground(True)
        self.modules[0].setStyleSheet("background-color: {}".format(self.color.name()))
        for mod in self.modules[1:]:
            mod.setStyleSheet("background-color: {}".format(QColor("green").lighter().name()))

class K2AO(Mod_Wrap):

    def __init__(self, *args, **kw_args):
        """Constructor"""

        super(K2AO, self).__init__("K2AO", QColor("green").lighter(), *args, **kw_args)

        self._color()

class NSPEC(Mod_Wrap):

    def __init__(self, *args, **kw_args):
        """Constructor"""

        super(NSPEC, self).__init__("NIRSPEC", QColor("yellow").lighter(), *args, **kw_args)

        self._color()

        self.modules = [
            QLabel("Pickoff"),
            QLabel("Fold Mir."),
            QLabel("Hatch"),
        ]

        self.modules[0].setToolTip("Pickoff is out")
        self.modules[1].setToolTip("Fold mirror is in")
        self.modules[2].setToolTip("Hatch is open (preferd state is closed)")

        for mod in self.modules:
            mod.setAlignment(Qt.AlignCenter)
            mod.setAutoFillBackground(True)
            mod.setStyleSheet("background-color: {}".format(QColor("green").lighter().name()))

        self.modules[-1].setStyleSheet("background-color: {}".format(self.color.name()))

class Scripts(Mod_Wrap):

    def __init__(self, *args, **kw_args):
        """Constructor"""

        super(Scripts, self).__init__("Scripts", QColor("green").lighter(), *args, **kw_args)

        self._color()