"""
AUTO from Python.  Every AUTO-window button is in `m.auto.buttons`; this
module adds a direct API on top:

    a = m.auto
    a.numerics(ds=0.01, dsmax=0.05, nmax=500, parmin=-0.2, parmax=0.5)
    br = a.run(param="iapp", start="steady")          # steady-state branch
    hb = a.diagram.special("HB")[0]
    po = a.run(grab=hb.label, choice="periodic")      # periodic orbits from the Hopf
    a.diagram.plot(y="v")                             # matplotlib

Point types follow XPP's labels: EP, BP, LP, HB, PD, TR, UZ, MX (and '' for
ordinary points).  Stability: AUTO stores it in the sign of the point
number; `Point.stable` decodes it.
"""
import ctypes
from dataclasses import dataclass, field

import numpy as np

from . import buttons as _buttons
from ._lib import XPPError

_NUMERICS = {  # python name -> AutoNum dialog field
    "ntst": "Ntst", "nmax": "Nmax", "npr": "NPr", "ds": "Ds", "dsmin": "Dsmin",
    "ncol": "Ncol", "epsl": "EPSL", "dsmax": "Dsmax", "parmin": "Par Min",
    "parmax": "Par Max", "normmin": "Norm Min", "normmax": "Norm Max",
    "epsu": "EPSU", "epss": "EPSS", "iad": "IAD", "mxbf": "MXBF", "iid": "IID",
    "itmx": "ITMX", "itnw": "ITNW", "nwtn": "NWTN", "iads": "IADS",
}
_PLOTS = {"hi": "h", "norm": "n", "hi-lo": "i", "hilo": "i", "period": "p",
          "two_par": "t", "twopar": "t", "frequency": "r", "average": "a"}


class CIDict(dict):
    """dict with case-insensitive string keys (XPP upper-cases names)"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._lower = {k.lower(): k for k in self}

    def __getitem__(self, k):
        return super().__getitem__(self._lower.get(str(k).lower(), k))

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def __contains__(self, k):
        return str(k).lower() in self._lower


def bif_type(itp):
    i = int(itp) % 10 if itp >= 0 else -((-int(itp)) % 10)
    return {1: "BP", 6: "BP", 2: "LP", 5: "LP", 3: "HB", -4: "UZ", 7: "PD",
            8: "TR", 9: "EP", -9: "MX"}.get(i, "")


@dataclass
class Point:
    """One point of the bifurcation diagram."""
    index: int          # position in the diagram list
    branch: int         # AUTO branch number (negative = periodic)
    pt: int             # AUTO point number (sign = stability)
    itp: int            # AUTO type code
    label: int          # 0 if unlabeled
    par: dict           # AUTO parameters at this point
    icp1: str           # main continuation parameter
    icp2: str           # second parameter (two-parameter runs)
    two_par: bool
    norm: float
    period: float
    u0: dict            # state (equilibrium, or orbit start)
    umax: dict          # max over the orbit (= u0 for equilibria)
    umin: dict          # min over the orbit
    ubar: dict          # orbit average
    eigenvalues: np.ndarray = field(repr=False)

    @property
    def type(self):
        return bif_type(self.itp)

    @property
    def stable(self):
        return self.pt < 0

    @property
    def periodic(self):
        return self.branch < 0

    @property
    def x(self):
        return self.par[self.icp1]


class Diagram:
    """The whole AUTO diagram as a list of Points, in the order AUTO stored
    them.  Consecutive points with the same branch form one curve."""

    def __init__(self, points, var_names):
        self.points = points
        self.vars = var_names

    def __len__(self):
        return len(self.points)

    def __getitem__(self, i):
        return self.points[i]

    def __iter__(self):
        return iter(self.points)

    def __repr__(self):
        lab = [f"{p.label}:{p.type}" for p in self.points if p.label]
        return f"<Diagram {len(self.points)} points, labels {' '.join(lab)}>"

    def labeled(self):
        return [p for p in self.points if p.label]

    def special(self, kind):
        return [p for p in self.points if p.type == kind.upper()]

    def label(self, n):
        for p in self.points:
            if p.label == n:
                return p
        raise KeyError(f"no point with label {n}")

    def branches(self):
        """Split into runs of consecutive points on the same branch."""
        out, cur = [], []
        for p in self.points:
            if cur and (p.branch != cur[-1].branch or p.icp1 != cur[-1].icp1
                        or p.two_par != cur[-1].two_par or abs(p.pt) <= abs(cur[-1].pt) - 0):
                out.append(Diagram(cur, self.vars))
                cur = []
            cur.append(p)
        if cur:
            out.append(Diagram(cur, self.vars))
        return out

    def table(self, y=None):
        """numpy structured array: param, y (max), y (min), stable, type..."""
        y = y or self.vars[0]
        dt = [("branch", int), ("pt", int), ("label", int), ("type", "U2"),
              ("par", float), ("par2", float), ("ymax", float), ("ymin", float),
              ("norm", float), ("period", float), ("stable", bool), ("periodic", bool)]
        rows = [(p.branch, p.pt, p.label, p.type, p.x, p.par.get(p.icp2, np.nan),
                 p.umax[y], p.umin[y], p.norm, p.period, p.stable, p.periodic)
                for p in self.points]
        return np.array(rows, dtype=dt)

    def to_pandas(self, y=None):
        import pandas as pd
        return pd.DataFrame(self.table(y))

    def plot(self, y=None, ax=None, two_par=False, label_points=True):
        """XPP-style diagram: red = stable, black = unstable; equilibria as
        lines, periodic orbits as filled (stable) / open (unstable) circles
        at max and min of y.  two_par=True plots par2 against par."""
        import matplotlib.pyplot as plt
        ax = ax or plt.gca()
        y = y or self.vars[0]
        for br in self.branches():
            pts = br.points
            if two_par != pts[0].two_par:
                continue
            xs = np.array([p.x for p in pts])
            if two_par:
                ys = np.array([p.par[p.icp2] for p in pts])
                ax.plot(xs, ys, "-", color="C0", lw=1.5)
                continue
            st = np.array([p.stable for p in pts])
            if pts[0].periodic:
                hi = np.array([p.umax[y] for p in pts])
                lo = np.array([p.umin[y] for p in pts])
                for s, mk in ((True, "o"), (False, "o")):
                    sel = st == s
                    kw = dict(ms=3, ls="none", marker=mk,
                              color="tab:green" if s else "tab:blue",
                              mfc=None if s else "none")
                    ax.plot(xs[sel], hi[sel], **kw)
                    ax.plot(xs[sel], lo[sel], **kw)
            else:
                ys = np.array([p.u0[y] for p in pts])
                # break the line where stability changes
                start = 0
                for k in range(1, len(pts) + 1):
                    if k == len(pts) or st[k] != st[start]:
                        sl = slice(max(start - 1, 0), k)
                        ax.plot(xs[sl], ys[sl], "-", color="red" if st[start] else "black",
                                lw=2 if st[start] else 1)
                        start = k
        if label_points:
            for p in self.points:
                if p.label and p.two_par == two_par and p.type not in ("", "EP"):
                    yy = p.par[p.icp2] if two_par else (p.umax[y] if p.periodic else p.u0[y])
                    ax.annotate(p.type, (p.x, yy), fontsize=7,
                                xytext=(3, 3), textcoords="offset points")
        ax.set_xlabel(self.points[0].icp1 if self.points else "")
        ax.set_ylabel((self.points[0].icp2 if self.points else "") if two_par else y)
        return ax


class Auto:
    """AUTO for one Model (m.auto)."""

    def __init__(self, model):
        self._m = model
        self._c = model._c
        self.buttons = _buttons.build_auto(model)

    # -- state ----------------------------------------------------------
    def open(self):
        """Create the (invisible) AUTO window; done automatically."""
        self._m._press_auto([], ())

    @property
    def settings(self):
        ints, dbl = (ctypes.c_int * 13)(), (ctypes.c_double * 14)()
        self._c.pyxpp_auto_settings(ints, dbl)
        npar = self._c.pyxpp_n_auto_par()
        pars = [self._c.pyxpp_auto_par_name(i).decode() for i in range(npar)]
        return {
            "ntst": ints[0], "nmax": ints[1], "npr": ints[2], "ncol": ints[3],
            "param": pars[ints[4]] if ints[4] < npar else None,
            "param2": pars[ints[5]] if ints[5] < npar else None,
            "y": self._m.vars[ints[6]] if ints[6] < len(self._m.vars) else ints[6],
            "plot": ints[7], "ips": ints[8], "nfpar": ints[9],
            "grabbed": ints[10] == 1, "grab_label": ints[11], "open": ints[12] == 1,
            "ds": dbl[0], "dsmin": dbl[1], "dsmax": dbl[2], "parmin": dbl[3],
            "parmax": dbl[4], "normmin": dbl[5], "normmax": dbl[6], "epsl": dbl[7],
            "epsu": dbl[8], "epss": dbl[9], "xmin": dbl[10], "xmax": dbl[11],
            "ymin": dbl[12], "ymax": dbl[13], "parameters": pars,
        }

    @property
    def diagram(self):
        n = self._c.pyxpp_diag_count()
        node = self._c.pyxpp_node()
        vars_ = self._m.vars[:node]
        npar = self._c.pyxpp_n_auto_par()
        pnames = [self._c.pyxpp_auto_par_name(i).decode() for i in range(npar)]
        ints, dbl = (ctypes.c_int * 9)(), (ctypes.c_double * 23)()
        vec = (ctypes.c_double * (6 * node))()
        pts = []
        for k in range(n):
            self._c.pyxpp_diag_get(k, ints, dbl, vec)
            v = np.frombuffer(vec, dtype=float).copy()
            uhi, ulo, u0, ubar = (v[j * node:(j + 1) * node] for j in range(4))
            ev = v[4 * node:5 * node] + 1j * v[5 * node:6 * node]
            par = CIDict({pnames[i]: dbl[3 + i] for i in range(npar)})
            pts.append(Point(
                index=k, branch=ints[0], pt=ints[1], itp=ints[2], label=ints[3],
                par=par,
                icp1=pnames[ints[4]] if 0 <= ints[4] < npar else str(ints[4]),
                icp2=pnames[ints[5]] if 0 <= ints[5] < npar else str(ints[5]),
                two_par=ints[6] > 0, norm=dbl[0], period=dbl[1],
                u0=CIDict(zip(vars_, u0)), umax=CIDict(zip(vars_, uhi)),
                umin=CIDict(zip(vars_, ulo)), ubar=CIDict(zip(vars_, ubar)),
                eigenvalues=ev))
        if ctypes.c_int.in_dll(self._c, "NBifs").value <= 1:
            pts = []  # only XPP's empty placeholder node
        return Diagram(pts, vars_)

    # -- dialogs ----------------------------------------------------------
    def parameters(self, *names):
        """Set AUTO's parameter list (Par1..Par8).  Parameters not listed
        cannot be continued."""
        if len(names) > 8:
            raise ValueError("AUTO takes at most 8 parameters")
        for n in names:
            if n not in self._m.pars:
                raise KeyError(f"no parameter {n!r}")
        d = {f"Par{i + 1}": n for i, n in enumerate(names)}
        self._m._press_auto(["p"], (d,))

    def numerics(self, **kw):
        """Continuation numerics: ntst nmax npr ds dsmin dsmax ncol epsl epsu
        epss parmin parmax normmin normmax iad mxbf iid itmx itnw nwtn iads"""
        d = {}
        for k, v in kw.items():
            if k.lower() not in _NUMERICS:
                raise KeyError(f"unknown AUTO numeric {k!r}; have {sorted(_NUMERICS)}")
            d[_NUMERICS[k.lower()]] = v
        if d:
            self._m._press_auto(["n"], (d,))

    def axes(self, plot="hi", y=None, param=None, param2=None,
             xmin=None, xmax=None, ymin=None, ymax=None):
        """Plot type and axes.  `param`/`param2` also choose the main and
        second continuation parameters, as in XPP."""
        key = _PLOTS.get(plot, plot)
        d = {}
        if y is not None:
            d["Y-axis"] = y
        if param is not None:
            self._ensure_param(param)
            d["Main Parm"] = param
        if param2 is not None:
            self._ensure_param(param2)
            d["Secnd Parm"] = param2
        for k, v in (("Xmin", xmin), ("Xmax", xmax), ("Ymin", ymin), ("Ymax", ymax)):
            if v is not None:
                d[k] = v
        self._m._press_auto(["a", key], (d,))

    def _ensure_param(self, name):
        cur = self.settings["parameters"]
        if any(c.lower() == name.lower() for c in cur):
            return
        new = list(cur)
        new[-1] = name
        self.parameters(*new)

    # -- actions ------------------------------------------------------------
    def grab(self, point):
        """Select a diagram point: a label (int), a Point, or '#k' / -1 for
        the k-th / last point."""
        if isinstance(point, Point):
            ans = str(point.label) if point.label else f"#{point.index}"
        elif isinstance(point, int) and point < 0:
            ans = f"#{point}"
        else:
            ans = str(point)
        self._m._press_auto(["g"], (ans,))

    def clear_grab(self):
        self._m._press_auto(["f", "c"], ())

    def reset(self):
        """Delete the diagram and AUTO's files (File > Reset diagram)."""
        self._m._press_auto(["f", "r"], (True,))

    def run(self, param=None, *, start=None, grab=None, choice=None, y=None,
            param2=None, answers=(), **numerics):
        """Run AUTO and return the new points as a Diagram.

        From scratch (nothing grabbed):  start = steady | periodic |
            bdry value | homoclinic | heteroclinic.  The current initial
            conditions must be (near) an equilibrium / orbit.
        From a point: grab=<label>, then choice = what XPP offers there:
            at HB: periodic | extend | new point | two param
            at LP: (two-parameter continuation, no choice)
            at BP: switch | extend | new point | two param
            on a periodic branch: extend | fixed period
            at PD: doubling | two param | fixed period | extend
            at TR: two param | fixed period | extend
        Remaining keyword arguments go to numerics().  `answers` are extra
        replies for anything else XPP asks.
        """
        if param is not None or y is not None or param2 is not None:
            self.axes(plot=self._plot_key(), y=y, param=param, param2=param2)
        if numerics:
            self.numerics(**numerics)
        if grab is not None:
            self.grab(grab)
        before = self._count()
        reply = []
        if not self.settings["grabbed"]:
            if start is None:
                raise ValueError("nothing grabbed: give start='steady' (or periodic, ...)")
            reply.append(start)
            if self._count() > 0:
                reply.append(True)  # "Destroy AUTO diagram & files?"
        elif choice is not None:
            reply.append(choice)
        reply.extend(answers)
        self._m._press_auto(["r"], reply)
        d = self.diagram
        new = [p for p in d.points if p.index >= before]
        return Diagram(new, d.vars)

    def _count(self):
        """number of real diagram points (XPP keeps one empty node until the
        first run)"""
        nb = ctypes.c_int.in_dll(self._c, "NBifs").value
        return self._c.pyxpp_diag_count() if nb > 1 else 0

    def _plot_key(self):
        return {0: "h", 1: "n", 2: "i", 3: "p", 4: "t", 10: "r", 11: "a"}.get(
            self.settings["plot"], "h")

    def write_pts(self, filename):
        """File > Write pts: XPP's text dump of the diagram."""
        self._m._press_auto(["f", "w"], (filename,))

    def save(self, filename):
        """File > Save diagram (reload with load())."""
        self._m._press_auto(["f", "s"], (filename,))

    def load(self, filename):
        """File > Load diagram."""
        self._m._press_auto(["f", "l"], (filename,))
