"""
pyxpp -- XPPAUT as a Python module, with no X11 interface.

    import pyxpp
    m = pyxpp.load("lecar.ode")
    tr = m.run(total=100)                 # Initialconds > Go
    m.buttons.sing_pts.go()               # any GUI button
    br = m.auto.run("iapp", start="steady")
    m.auto.diagram.plot(y="v")
"""
from ._lib import ESC, XPPError
from .auto import Auto, Diagram, Point
from .buttons import show
from .model import AnswersNotUsed, Equilibrium, Model, Trajectory, load

__all__ = ["load", "Model", "Trajectory", "Equilibrium", "Auto", "Diagram", "Point",
           "XPPError", "AnswersNotUsed", "ESC", "show"]
__version__ = "0.1.0"
