"""
Every XPPAUT menu button as a Python call.

The tree mirrors the XPP GUI exactly, including the keyboard shortcuts:

    m.buttons.initialconds.go()            # I G
    m.buttons.initialconds.new(-0.3, 0.1)  # I N, answers the IC prompts
    m.buttons.numerics.total(200)          # U T 200
    m.buttons.numerics.method("cvode")     # U M C
    m.buttons.sing_pts.go()                # S G
    m.buttons.file.write_set("x.set")      # F W x.set
    m.auto.buttons.run("steady")           # AUTO: Run, Steady state

Positional arguments are the answers to whatever the button asks next, in
the order XPP asks (a prompt, a menu choice, a dialog given as a dict, a
file name, a yes/no as True/False).  Missing answers take XPP's default,
exactly as if Enter were pressed.  After each call, ``m.transcript`` shows
what was asked and answered.

`show(m.buttons)` prints the whole tree.
"""
from ._lib import ESC


# Each node: (key, python_name, label, hint, children-or-None)
def _n(key, name, label, hint="", children=None):
    return (key, name, label, hint, children)


MAIN = [
    _n("i", "initialconds", "Initialconds", "Integrate the equations", [
        _n("r", "range", "(R)ange", "Integrate over a range of parameters, init data, etc"),
        _n("2", "two_par_range", "(2)par range", "Integrate over range of 2 parameters, init data, etc"),
        _n("l", "last", "(L)ast", "Pick up from last step of previous solution"),
        _n("o", "old", "(O)ld", "Use current initial data"),
        _n("g", "go", "(G)o", "Use current initial data"),
        _n("m", "mouse", "(M)ouse", "Specify initial data with mouse (answer: 'ix,iy' pixels)"),
        _n("s", "shift", "(S)hift", "Pick up from last step and shift T to latest time"),
        _n("n", "new", "(N)ew", "Input new initial data, one prompt per variable"),
        _n("h", "shoot", "s(H)oot", "Use the initial data from last shooting from fixed pt"),
        _n("f", "file", "(F)ile", "Read init data from file"),
        _n("u", "formula", "form(U)la", "Type in function of 't' for t^th equation"),
        _n("i", "mice", "m(I)ce", "Repeated ICs using mouse"),
        _n("d", "dae_guess", "DAE guess", "Guess new values for DAE"),
        _n("b", "backward", "(B)ackward", "Integrate backwards"),
    ]),
    _n("c", "continue_", "Continue", "Continue integration for specified time"),
    _n("n", "nullcline", "Nullcline", "Draw nullclines", [
        _n("n", "new", "(N)ew", "Compute new nullclines"),
        _n("r", "restore", "(R)estore", "Redraw last nullclines"),
        _n("a", "auto", "(A)uto", "Set automatic redraw"),
        _n("m", "manual", "(M)anual", "Only redraw when asked"),
        _n("f", "freeze", "(F)reeze", "Freeze multiple nullclines", [
            _n("f", "freeze", "(F)reeze", "Freeze current clines"),
            _n("d", "delete_all", "(D)elete all", "Delete all frozen clines"),
            _n("r", "range", "(R)ange", "Range freeze a bunch of clines"),
            _n("a", "animate", "(A)nimate", "Animate nullclines"),
        ]),
        _n("s", "save", "(S)ave", "Save nullcline values to a file"),
    ]),
    _n("d", "dir_field", "Dir.field/flow", "Direction fields and flows of the phaseplane", [
        _n("d", "direct_field", "(D)irect Field", "Draw vector field for 2D section"),
        _n("f", "flow", "(F)low", "Draw regular series of trajectories"),
        _n("n", "no_dir_field", "(N)o dir. fld.", ""),
        _n("c", "colorize", "(C)olorize", "Color the PP on a grid"),
        _n("s", "scaled_dir_field", "(S)caled Dir.Fld", "Draw only directions"),
    ]),
    _n("w", "window", "Window/zoom", "Change the size of two-dimensional view", [
        _n("w", "window", "(W)indow", "Manually choose 2D view"),
        _n("z", "zoom_in", "(Z)oom In", "Zoom in (answer: 'x1,y1,x2,y2' pixels)"),
        _n("o", "zoom_out", "Zoom (O)ut", "Zoom out (answer: 'x1,y1,x2,y2' pixels)"),
        _n("f", "fit", "(F)it", "Let XPP automatically choose window"),
        _n("d", "default", "(D)efault", "Reset to default view"),
        _n("s", "scroll", "(S)croll", "Scroll around the view"),
    ]),
    _n("a", "phasespace", "phAsespace", "Set up periodic/torus phase space", [
        _n("a", "all", "(A)ll", "Each variable is on a circle"),
        _n("n", "none", "(N)one", "No variable on circle"),
        _n("c", "choose", "(C)hoose", "Choose circle variables"),
    ]),
    _n("k", "kinescope", "Kinescope", "Take snapshots of the screen", [
        _n("c", "capture", "(C)apture", "Grab a screen shot"),
        _n("r", "reset", "(R)eset", "Clear all screen shots"),
        _n("p", "playback", "(P)layback", "Manually cycle thru screenshots"),
        _n("a", "autoplay", "(A)utoplay", "Continuously cycle through screen shots"),
        _n("s", "save", "(S)ave", "Dump the screen shots to disk"),
        _n("m", "make_anigif", "(M)ake AniGif", "Make animated gif file from screenshots"),
    ]),
    _n("g", "graphic_stuff", "Graphic stuff", "Adding graphs, hard copy, etc", [
        _n("a", "add_curve", "(A)dd curve", "Add another curve to the current plot"),
        _n("d", "delete_last", "(D)elete last", "Delete last added plot"),
        _n("r", "remove_all", "(R)emove all", "Remove all the added plots except the main one"),
        _n("e", "edit_curve", "(E)dit curve", "Edit parameters for a plot"),
        _n("p", "postscript", "(P)ostscript", "Create a postscript file of current plot"),
        _n("v", "svg", "S(V)G", "Create a styleable svg file of current plot"),
        _n("f", "freeze", "(F)reeze", "Options for permanently saving curve", [
            _n("f", "freeze", "(F)reeze", ""),
            _n("d", "delete", "(D)elete", ""),
            _n("e", "edit", "(E)dit", ""),
            _n("r", "remove_all", "(R)emove all", ""),
            _n("k", "key", "(K)ey", "", [
                _n("n", "no_key", "(N)o key", ""),
                _n("k", "key", "(K)ey", ""),
            ]),
            _n("b", "bif_diag", "(B)if.Diag", "Import a bifurcation diagram"),
            _n("c", "clear_bd", "(C)lr. BD", ""),
            _n("o", "toggle_freeze", "(O)n/(O)ff freeze", ""),
        ]),
        _n("x", "axes_opts", "a(X)es opts", "Axes label sizes and zero axes for postscript"),
        _n("o", "export_data", "exp(O)rt data", "Export the numbers used in the graphs on the screen"),
        _n("c", "colormap", "(C)olormap", "Change colormap", [
            _n("n", "normal", "(N)ormal", ""),
            _n("p", "periodic", "(P)eriodic", ""),
            _n("h", "hot", "(H)ot", ""),
            _n("c", "cool", "(C)ool", ""),
            _n("b", "blue_red", "(B)lue-red", ""),
            _n("g", "gray", "(G)ray", ""),
            _n("u", "cubehelix", "c(U)behelix", ""),
        ]),
    ]),
    _n("u", "numerics", "nUmerics", "Numerics options", "NUMERICS"),
    _n("f", "file", "File", "Quit, save stuff, etc", "FILE"),
    _n("p", "parameters", "Parameters", "Change problem parameters (answer: name, value, ..., then '')"),
    _n("e", "erase", "Erase", "Clear screen"),
    _n("m", "makewindow", "Makewindow", "Create other windows", [
        _n("c", "create", "(C)reate", ""),
        _n("k", "kill_all", "(K)ill all", ""),
        _n("d", "destroy", "(D)estroy", ""),
        _n("b", "bottom", "(B)ottom", ""),
        _n("a", "auto", "(A)uto", ""),
        _n("m", "manual", "(M)anual", ""),
        _n("s", "simplot", "(S)imPlot", ""),
    ]),
    _n("t", "text_etc", "Text,etc", "Add fancy text and lines, arrows", [
        _n("t", "text", "(T)ext", ""),
        _n("a", "arrow", "(A)rrow", ""),
        _n("p", "pointer", "(P)ointer", ""),
        _n("m", "marker", "(M)arker", ""),
        _n("e", "edit", "(E)dit", "", [
            _n("m", "move", "(M)ove", ""),
            _n("c", "change", "(C)hange", ""),
            _n("d", "delete", "(D)elete", ""),
        ]),
        _n("d", "delete_all", "(D)elete all", ""),
        _n("s", "markers", "marker(S)", ""),
    ]),
    _n("s", "sing_pts", "Sing pts", "Find fixed points and stability", [
        _n("g", "go", "(G)o", "Newton from current initial data"),
        _n("m", "mouse", "(M)ouse", "Newton from a clicked guess"),
        _n("r", "range", "(R)ange", "Track equilibria over a parameter range"),
        _n("c", "monte_carlo", "monte(C)ar", "Search for equilibria from random guesses"),
    ]),
    _n("v", "viewaxes", "Viewaxes", "Change 2 or 3d views", [
        _n("2", "two_d", "2D", ""),
        _n("3", "three_d", "3D", ""),
        _n("a", "array", "Array", ""),
        _n("t", "toon", "Toon", ""),
    ]),
    _n("x", "xi_vs_t", "Xi vs t", "Plot variable vs time"),
    _n("r", "restore", "Restore", "Redraw the graph"),
    _n("3", "params_3d", "3d-params", "Set parameters for 3D view"),
    _n("b", "bndryval", "Bndryval", "Run boundary value solver", [
        _n("r", "range", "(R)ange", ""),
        _n("n", "no_show", "(N)o show", ""),
        _n("s", "show", "(S)how", ""),
        _n("p", "periodic", "(P)eriodic", ""),
    ]),
]

NUMERICS = [
    _n("t", "total", "Total", "Total time to integrate eqns"),
    _n("s", "start_time", "Start time", "Starting time -- T0"),
    _n("r", "transient", "tRansient", "Time to integrate before storing"),
    _n("d", "dt", "Dt", "Time step to use"),
    _n("n", "ncline_ctrl", "Ncline ctrl", "Mesh for nullclines"),
    _n("i", "sing_pt_ctrl", "sIng pt ctrl", "Numerical parameters for fixed points"),
    _n("o", "noutput", "nOutput", "Number of steps per plotted point"),
    _n("b", "bounds", "Bounds", "Maximum allowed size of any variable"),
    _n("m", "method", "Method", "Integration method", [
        _n("d", "discrete", "(D)iscrete", ""),
        _n("e", "euler", "(E)uler", ""),
        _n("m", "mod_euler", "(M)od. Euler", ""),
        _n("r", "runge_kutta", "(R)unge-Kutta", ""),
        _n("a", "adams", "(A)dams", ""),
        _n("g", "gear", "(G)ear", ""),
        _n("v", "volterra", "(V)olterra", ""),
        _n("b", "backeul", "(B)ackEul", ""),
        _n("q", "qualst_rk4", "(Q)ualst.RK4", ""),
        _n("s", "stiff", "(S)tiff", ""),
        _n("c", "cvode", "(C)Vode", ""),
        _n("5", "dopri5", "DoPri(5)", ""),
        _n("8", "dopri83", "DoPri(8)3", ""),
        _n("2", "rosen23", "Rosen(2)3", ""),
        _n("y", "symplectic", "sYmplectic", ""),
    ]),
    _n("e", "delay", "dElay", "Maximum delay and delay related stuff"),
    _n("c", "color_code", "Color code", "Color trajectories according to velocity, etc", [
        _n("n", "no_color", "(N)o color", ""),
        _n("v", "velocity", "(V)elocity", ""),
        _n("a", "another_quantity", "(A)nother quantity", ""),
    ]),
    _n("h", "stochast", "stocHast", "Curve fitting, FFT, mean, variance, seed, etc", [
        _n("n", "new_seed", "New seed", ""),
        _n("c", "compute", "Compute", ""),
        _n("d", "data", "Data", ""),
        _n("m", "mean", "Mean", ""),
        _n("v", "variance", "Variance", ""),
        _n("h", "histogram", "Histogram", ""),
        _n("o", "old_hist", "Old hist", ""),
        _n("f", "fourier", "Fourier", ""),
        _n("p", "power", "Power", ""),
        _n("i", "fit_data", "fIt data", ""),
        _n("s", "stat", "Stat", ""),
        _n("l", "liapunov", "Liapunov", ""),
        _n("a", "autocor", "stAutocor", ""),
        _n("x", "xcorrel", "Xcorrel etc", ""),
        _n("e", "spec_dns", "spEc.dns", ""),
        _n("2", "hist_2d", "2D-hist", ""),
    ]),
    _n("p", "poincare_map", "Poincare map", "Define Poincare map parameters", [
        _n("n", "none", "(N)one", ""),
        _n("s", "section", "(S)ection", ""),
        _n("m", "max_min", "(M)ax/min", ""),
        _n("p", "period", "(P)eriod", ""),
    ]),
    _n("u", "ruelle_plot", "rUelle plot", "Define shifted plots"),
    _n("k", "lookup", "looKup", "Modify lookup tables", [
        _n("e", "edit", "(E)dit", ""),
        _n("v", "view", "(V)iew", ""),
    ]),
    _n("v", "bndval", "bndVal", "Numerical setup for boundary value solver"),
    _n("a", "averaging", "Averaging", "Compute adjoint and averaged functions", [
        _n("n", "new_adj", "(N)ew adj", ""),
        _n("m", "make_h", "(M)ake H", ""),
        _n("a", "adjoint", "(A)djoint", ""),
        _n("o", "orbit", "(O)rbit", ""),
        _n("h", "hfun", "(H)fun", ""),
        _n("p", "parameters", "(P)arameters", ""),
        _n("r", "range", "(R)ange", ""),
    ]),
]

FILE = [
    _n("p", "prt_src", "Prt src", "Display source and active comments"),
    _n("w", "write_set", "Write set", "Save information for restart"),
    _n("r", "read_set", "Read set", "Read information for restart"),
    _n("a", "auto", "Auto", "Open AUTO (same as m.auto)"),
    _n("c", "calculator", "Calculator", "Each answer is an expression; returns results in transcript"),
    _n("e", "edit", "Edit", "Edit right-hand sides or functions", [
        _n("r", "rhs", "RHS's", "Answer: dict {var: new rhs}"),
        _n("f", "functions", "Functions", ""),
        _n("s", "save_as", "Save as", ""),
        _n("l", "load_dll", "Load DLL", ""),
    ]),
    _n("s", "save_info", "Save info", "Save info about simulation in human readable format"),
    _n("b", "bell", "Bell on/off", "Turn bell on/off"),
    _n("h", "help", "Help", "Browser help"),
    _n("q", "quit", "Quit", "Quit (disabled in pyxpp: raises XPPError)"),
    _n("t", "transpose", "Transpose", "Transpose storage"),
    _n("i", "tips", "tIps", "Turn off tips"),
    _n("g", "get_par_set", "Get par set", "Set predefined parameters ('set' blocks in the .ode)"),
    _n("l", "clone", "cLone", "Clone the ode file"),
    _n("x", "xpprc", ".Xpprc", "Edit your .xpprc preferences file"),
    _n("u", "tutorial", "tUtorial", "Run a quick tutorial on XPPAUT"),
]

AUTO = [
    _n("p", "parameter", "Parameter", "Choose up to 8 AUTO parameters (dialog Par1..Par8)"),
    _n("a", "axes", "Axes", "Plot type and axes", [
        _n("h", "hi", "Hi", ""), _n("n", "norm", "Norm", ""), _n("i", "hi_lo", "hI-lo", ""),
        _n("p", "period", "Period", ""), _n("t", "two_par", "Two par", ""),
        _n("z", "zoom_in", "(Z)oom in", ""), _n("o", "zoom_out", "Zoom (O)ut", ""),
        _n("1", "last_1_par", "last 1 par", ""), _n("2", "last_2_par", "last 2 par", ""),
        _n("f", "fit", "Fit", ""), _n("r", "frequency", "fRequency", ""),
        _n("a", "average", "Average", ""), _n("d", "default", "Default", ""),
        _n("s", "scroll", "Scroll", ""),
    ]),
    _n("n", "numerics", "Numerics", "Continuation numerics (dialog AutoNum)"),
    _n("r", "run", "Run", "Run AUTO; asks what to do at the grabbed point"),
    _n("g", "grab", "Grab", "Pick a point: label n, or '#k' for the k-th point"),
    _n("u", "usr_period", "Usr period", "User-defined output values"),
    _n("c", "clear", "Clear", "Clear the plot"),
    _n("d", "redraw", "reDraw", "Redraw the diagram"),
    _n("f", "file", "File", "Diagram files", [
        _n("i", "import_orbit", "Import orbit", ""),
        _n("s", "save_diagram", "Save diagram", ""),
        _n("l", "load_diagram", "Load diagram", ""),
        _n("p", "postscript", "Postscript", ""),
        _n("v", "svg", "SVG", ""),
        _n("r", "reset_diagram", "Reset diagram", ""),
        _n("c", "clear_grab", "Clear grab", ""),
        _n("w", "write_pts", "Write pts", ""),
        _n("a", "all_info", "All info", ""),
        _n("d", "init_data", "init Data", ""),
        _n("t", "toggle_redraw", "Toggle redraw", ""),
        _n("n", "auto_range", "auto raNge", ""),
        _n("e", "select_2par_pt", "sElect 2par pt", ""),
        _n("b", "draw_labeled", "draw laBled", ""),
        _n("o", "load_branch", "lOad branch", ""),
    ]),
]


class Button:
    """A callable XPP button.  Calling it runs the button and answers
    whatever XPP asks with the positional arguments."""

    def __init__(self, model, press, path, label, hint):
        self._model, self._press, self._path = model, press, path
        self._label, self.__doc__ = label, hint or label

    def __call__(self, *answers):
        return self._press(self._path, answers)

    def __repr__(self):
        keys = " ".join(k.upper() if k != ESC else "Esc" for k in self._path)
        return f"<button {self._label!r} keys={keys}>"


class Menu(Button):
    """A button that opens a submenu.  Its children are attributes; calling
    it directly opens the menu and lets you answer it yourself."""

    def __init__(self, model, press, path, label, hint, children):
        super().__init__(model, press, path, label, hint)
        self._children = []
        for key, name, lab, h, sub in children:
            p = path + [key]
            if sub is None:
                b = Button(model, press, p, lab, h)
            else:
                b = Menu(model, press, p, lab, h, sub)
            setattr(self, name, b)
            self._children.append(name)

    def __dir__(self):
        return list(self._children)

    def __repr__(self):
        return f"<menu {self._label!r}: {', '.join(self._children)}>"


def build_main(model):
    """m.buttons"""
    root = Menu(model, None, [], "XPP", "", [])
    for key, name, lab, h, sub in MAIN:
        if sub == "NUMERICS":
            b = Menu(model, model._press_numerics, [], lab, h, NUMERICS)
        elif sub == "FILE":
            b = Menu(model, model._press_file, [], lab, h, FILE)
        elif sub is None:
            b = Button(model, model._press_main, [key], lab, h)
        else:
            b = Menu(model, model._press_main, [key], lab, h, sub)
        setattr(root, name, b)
        root._children.append(name)
    return root


def build_auto(model):
    """m.auto.buttons"""
    return Menu(model, model._press_auto, [], "AUTO", "", AUTO)


def show(menu, indent=0, out=None):
    """Print a button tree."""
    lines = [] if out is None else out
    for name in menu._children:
        b = getattr(menu, name)
        keys = "".join(b._path[-1:]).upper()
        lines.append(f"{'  ' * indent}{name:<22} [{keys}]  {b.__doc__ or ''}".rstrip())
        if isinstance(b, Menu):
            show(b, indent + 1, lines)
    if out is None:
        print("\n".join(lines))
