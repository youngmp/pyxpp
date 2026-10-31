"""
Model: one loaded .ode file running in its own private copy of XPPAUT.
"""
import ctypes
import os
import re
import warnings
from pathlib import Path

import numpy as np

from ._lib import ESC, Lib, XPPError, format_answer, new_workdir
from . import buttons as _buttons

METHODS = ["discrete", "euler", "modeuler", "rungekutta", "adams", "gear", "volterra",
           "backeul", "qualrk", "stiff", "cvode", "5dp", "83dp", "2rb", "ymp"]
# XPP's own key letters for METH=..., same order as METHODS
_METHOD_KEYS = "demragvbqsc582y"
_METHOD_ALIASES = {
    "rk4": "r", "runge-kutta": "r", "rungekutta": "r", "runge_kutta": "r",
    "discrete": "d", "euler": "e", "modeuler": "m", "mod_euler": "m", "adams": "a",
    "gear": "g", "volterra": "v", "backeul": "b", "qualrk": "q", "qualst": "q",
    "stiff": "s", "cvode": "c", "dopri5": "5", "dp5": "5", "5dp": "5", "dopri83": "8",
    "dp83": "8", "83dp": "8", "rosen23": "2", "rb23": "2", "2rb": "2", "symplectic": "y",
    "ymp": "y",
}


class AnswersNotUsed(UserWarning):
    """Some answers passed to a button were never asked for."""


class Trajectory:
    """Contents of XPP's data browser: column 0 is t, then every variable and
    auxiliary quantity in .ode order.  Index by name or use .array."""

    def __init__(self, array, names):
        self.array = array
        self.names = list(names)
        self._idx = {n.lower(): i for i, n in enumerate(self.names)}

    def __getitem__(self, name):
        if isinstance(name, str):
            try:
                return self.array[:, self._idx[name.lower()]]
            except KeyError:
                raise KeyError(f"{name!r}; columns are {self.names}") from None
        return self.array[name]

    def __len__(self):
        return self.array.shape[0]

    def __repr__(self):
        return f"<Trajectory {self.array.shape[0]} rows x {self.names}>"

    @property
    def t(self):
        return self.array[:, 0]

    def to_pandas(self):
        import pandas as pd
        return pd.DataFrame(self.array, columns=self.names)


class Equilibrium:
    def __init__(self, x, eigenvalues, discrete=False):
        self.x = x
        self.eigenvalues = eigenvalues
        if discrete:
            self.stable = bool(np.all(np.abs(eigenvalues) < 1))
        else:
            self.stable = bool(np.all(eigenvalues.real < 0))

    def __repr__(self):
        xs = ", ".join(f"{k}={v:.6g}" for k, v in self.x.items())
        return f"<Equilibrium {'stable' if self.stable else 'unstable'} {xs}>"


class _Named:
    """dict-like view onto parameters or initial conditions"""

    def __init__(self, model, names, getter, setter, kind):
        self._m, self._names = model, names
        self._get, self._set, self._kind = getter, setter, kind

    def _key(self, name):
        for n in self._names:
            if n.lower() == name.lower():
                return n
        raise KeyError(f"no {self._kind} {name!r}; have {self._names}")

    def __getitem__(self, name):
        return self._get(self._key(name))

    def __setitem__(self, name, value):
        self._set(self._key(name), float(value))

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)

    def __contains__(self, name):
        return any(n.lower() == str(name).lower() for n in self._names)

    def keys(self):
        return list(self._names)

    def items(self):
        return [(n, self[n]) for n in self._names]

    def update(self, d=None, **kw):
        for k, v in {**(d or {}), **kw}.items():
            self[k] = v

    def as_dict(self):
        return dict(self.items())

    def __repr__(self):
        return f"{self._kind}s(" + ", ".join(f"{k}={v:g}" for k, v in self.items()) + ")"


class Model:
    """
    A running XPPAUT session without the X11 interface.

        m = pyxpp.load("lecar.ode")
        m.pars["iapp"] = 0.1
        tr = m.run(total=200)            # Initialconds > Go
        eq = m.equilibrium()             # Sing pts, non-interactive
        m.buttons.numerics.dt(0.01)      # any GUI button
        m.auto.run(...)                  # bifurcation diagrams

    Parameters
    ----------
    path : .ode file.  `text=` may be given instead (written to the workdir).
    workdir : where XPP writes its files (default: fresh temp dir).  XPP is
        run with this as the current directory during calls that write files.
    quiet : send XPP/AUTO terminal output to `m.log` instead of stdout.
    args : extra XPP command-line arguments, e.g. ["-setfile", "x.set"].
    """

    def __init__(self, path=None, *, text=None, workdir=None, quiet=True, args=()):
        if (path is None) == (text is None):
            raise ValueError("give exactly one of path or text")
        self.workdir = Path(workdir) if workdir else new_workdir()
        self.workdir.mkdir(parents=True, exist_ok=True)
        if text is not None:
            path = self.workdir / "model.ode"
            path.write_text(text if text.endswith("\n") else text + "\n")
        self.path = Path(path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.quiet = quiet
        self._lib = Lib(self.workdir / ".pyxpp")
        self._c = self._lib.c
        autodir = self.workdir / ".pyxpp" / "auto"
        autodir.mkdir(parents=True, exist_ok=True)
        self._c.pyxpp_set_auto_dir(str(autodir).encode())

        argv = [b"xppaut", str(self.path).encode(), *[str(a).encode() for a in args]]
        arr = (ctypes.c_char_p * len(argv))(*argv)
        with self._call():
            rc = self._c.pyxpp_init(len(argv), arr, str(self._lib.logpath).encode())
        if rc != 0:
            raise XPPError(f"loading {self.path.name} failed: "
                           f"{self._c.pyxpp_error().decode()}\n--- XPP log ---\n{self.log[-3000:]}")

        node, nmark, neq = self._c.pyxpp_node(), self._c.pyxpp_nmarkov(), self._c.pyxpp_neq()
        allnames = [self._c.pyxpp_var_name(i).decode() for i in range(neq)]
        self.vars = allnames[:node + nmark]
        self.aux = allnames[node + nmark:neq]
        self.columns = ["t"] + allnames
        self.par_names = [self._c.pyxpp_par_name(i).decode() for i in range(self._c.pyxpp_npar())]

        self._last_ic = (ctypes.c_double * 1).in_dll(self._c, "last_ic")
        addr = ctypes.addressof(self._last_ic)
        self._last_ic = (ctypes.c_double * max(1, len(self.vars))).from_address(addr)

        self.pars = _Named(self, self.par_names, self._get_val, self._set_val, "parameter")
        self.ics = _Named(self, self.vars, self._get_ic, self._set_ic, "initial condition")
        self.buttons = _buttons.build_main(self)
        from .auto import Auto
        self.auto = Auto(self)
        self._last_transcript = ""

    # ------------------------------------------------------------------
    # plumbing
    # ------------------------------------------------------------------
    def _call(self):
        """context: chdir to workdir and capture C stdout"""
        model = self

        class _Ctx:
            def __enter__(self):
                self.cwd = os.getcwd()
                os.chdir(model.workdir)
                self.cap = model._lib.captured(model.quiet)
                self.cap.__enter__()

            def __exit__(self, *exc):
                self.cap.__exit__(*exc)
                os.chdir(self.cwd)
                return False
        return _Ctx()

    def _run(self, fn, *args, answers=()):
        self._c.pyxpp_transcript_clear()
        self._lib.tape(answers)
        with self._call():
            rc = fn(*args)
        self._last_transcript = self._c.pyxpp_transcript().decode(errors="replace")
        left = self._lib.leftover()
        self._c.pyxpp_tape_clear()
        if rc != 0:
            msg = self._c.pyxpp_error().decode(errors="replace")
            raise XPPError(msg + (f"\n--- transcript ---\n{self._last_transcript}"
                                  if self._last_transcript else ""))
        if left:
            warnings.warn(f"{left} answer(s) were not asked for.\n"
                          f"--- transcript ---\n{self._last_transcript}",
                          AnswersNotUsed, stacklevel=4)
        return self._last_transcript

    def _press_main(self, path, answers):
        self._c.pyxpp_main_menu()
        return self._run(self._c.pyxpp_key, ord(path[0]), answers=[*path[1:], *answers])

    def _press_numerics(self, path, answers):
        if not path:
            return ""
        return self._run(self._c.pyxpp_num_key, ord(path[0]), answers=[*path[1:], *answers])

    def _press_file(self, path, answers):
        if not path:
            return ""
        self._c.pyxpp_main_menu()
        self._c.pyxpp_key(ord("f"))
        return self._run(self._c.pyxpp_key, ord(path[0]), answers=[*path[1:], *answers])

    def _press_auto(self, path, answers):
        if not path:
            return self._run(self._c.pyxpp_auto_open)
        return self._run(self._c.pyxpp_auto_key, ord(path[0]), answers=[*path[1:], *answers])

    def press(self, key, *answers):
        """Press one key in XPP's main window and answer what it asks.
        `m.press("i", "g")` is Initialconds > Go."""
        if key in ("\x1b", "esc", "Esc", "ESC"):
            self._c.pyxpp_main_menu()
            return ""
        return self._press_main([key], answers)

    def command(self, com, *answers):
        """Run an internal XPP command id (the M_* constants in menudrive.h)."""
        return self._run(self._c.pyxpp_command, int(com), answers=answers)

    @property
    def transcript(self):
        """Questions XPP asked during the last call and the answers used."""
        return self._last_transcript

    @property
    def log(self):
        """Everything XPP and AUTO printed so far."""
        self._c.pyxpp_flush_log()
        try:
            return self._lib.logpath.read_text(errors="replace")
        except FileNotFoundError:
            return ""

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------
    def _get_val(self, name):
        v = ctypes.c_double()
        if self._c.pyxpp_get_val(name.encode(), ctypes.byref(v)) != 0:
            raise KeyError(name)
        return v.value

    def _set_val(self, name, value):
        if self._c.pyxpp_set_val(name.encode(), value) != 0:
            raise KeyError(name)

    def _get_ic(self, name):
        return self._last_ic[self.vars.index(name)]

    def _set_ic(self, name, value):
        self._last_ic[self.vars.index(name)] = value

    def get(self, name):
        """Current value of any parameter, variable or derived quantity."""
        if name in self.ics:
            return self.ics[name]
        return self._get_val(name)

    def set(self, **options):
        """Set parameters, initial conditions and @-options in one call.

            m.set(iapp=0.1, v=-0.3, total=200, dt=0.01, meth="cvode")

        Names are tried as parameter, then variable (initial condition),
        then as an XPP @ option (anything legal on an `@` line).
        """
        for k, v in options.items():
            if k in self.pars:
                self.pars[k] = v
            elif k in self.ics:
                self.ics[k] = v
            else:
                self.set_option(k, v)
        return self

    def set_option(self, name, value):
        """Exactly like `@ name=value` in the .ode file."""
        if name.lower() in ("meth", "method"):
            value = method_key(value)
        r = self._c.pyxpp_set_option(str(name).encode(), format_answer(value).encode())
        if r != 0:
            raise XPPError(self._c.pyxpp_error().decode())

    @property
    def numerics(self):
        """Main integration settings (read-only snapshot; change with set())."""
        g = lambda t, n: t.in_dll(self._c, n).value  # noqa: E731
        d = ctypes.c_double
        i = ctypes.c_int
        return {
            "total": g(d, "TEND"), "dt": g(d, "DELTA_T"), "t0": g(d, "T0"),
            "trans": g(d, "TRANS"), "nout": g(i, "NJMP"), "bound": g(d, "BOUND"),
            "meth": METHODS[g(i, "METHOD")] if 0 <= g(i, "METHOD") < len(METHODS) else g(i, "METHOD"),
            "tol": g(d, "TOLER"), "atol": g(d, "ATOLER"), "dtmin": g(d, "HMIN"),
            "dtmax": g(d, "HMAX"), "maxstor": g(i, "MAXSTOR"), "delay": g(d, "DELAY"),
            "newt_tol": g(d, "NEWT_ERR"), "evec_tol": g(d, "EVEC_ERR"),
            "newt_iter": g(i, "EVEC_ITER"), "poimap": g(i, "POIMAP"),
        }

    # ------------------------------------------------------------------
    # integration
    # ------------------------------------------------------------------
    @property
    def data(self):
        """The data browser (last integration) as a Trajectory."""
        rows, cols = self._c.pyxpp_data_rows(), self._c.pyxpp_data_cols()
        out = np.empty((rows, cols), dtype=float)
        if rows:
            self._c.pyxpp_data_copy(out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
        return Trajectory(out, self.columns[:cols])

    def run(self, **settings):
        """Integrate from the current initial conditions (Initialconds > Go)
        and return the trajectory.  Keyword arguments go through set()."""
        if settings:
            self.set(**settings)
        self._press_main(["i", "g"], ())
        return self.data

    def run_last(self, **settings):
        """Integrate from the end of the previous run (Initialconds > Last)."""
        if settings:
            self.set(**settings)
        self._press_main(["i", "l"], ())
        return self.data

    def continue_run(self, total):
        """Continue the current run until time `total` (Continue button)."""
        self._press_main(["c"], (total,))
        return self.data

    def last_point(self):
        """Final state of the last run as {var: value}."""
        d = self.data
        if len(d) == 0:
            raise XPPError("no data; run first")
        return {v: float(d[v][-1]) for v in self.vars}

    def sweep(self, name, values, **settings):
        """Run once per value of parameter (or initial condition) `name`,
        restoring it afterwards.  Returns a list of Trajectories.  (The GUI's
        Initialconds > Range is also available as a button.)"""
        target = self.pars if name in self.pars else self.ics
        old = target[name]
        out = []
        try:
            for v in values:
                target[name] = v
                out.append(self.run(**settings))
        finally:
            target[name] = old
        return out

    # ------------------------------------------------------------------
    # phase plane
    # ------------------------------------------------------------------
    def view(self, x=None, y=None, xlo=None, xhi=None, ylo=None, yhi=None):
        """Set the 2D view (Viewaxes > 2D).  Nullclines and direction fields
        are computed in this window, as in the GUI."""
        d = {}
        for k, v in (("X-axis", x), ("Y-axis", y), ("Xmin", xlo), ("Xmax", xhi),
                     ("Ymin", ylo), ("Ymax", yhi)):
            if v is not None:
                d[k] = v
        self._press_main(["v", "2"], (d,))

    def nullclines(self, x=None, y=None, xlo=None, xhi=None, ylo=None, yhi=None, mesh=None):
        """Compute nullclines in the current (or given) 2D view.  Returns
        {xvar: array (N,2), yvar: array (N,2)}; NaN rows separate pieces.
        Key xvar is the nullcline of the x-axis variable (its rhs = 0)."""
        if any(v is not None for v in (x, y, xlo, xhi, ylo, yhi)):
            self.view(x, y, xlo, xhi, ylo, yhi)
        if mesh is not None:
            self._press_numerics(["n"], (mesh,))
        self._press_main(["n", "n"], ())
        fname = ".pyxpp/nullclines.dat"
        path = self.workdir / fname
        if path.exists():
            path.unlink()
        self._press_main(["n", "s"], (fname,))
        if not path.exists():
            raise XPPError("XPP did not compute nullclines (is the view 2D "
                           "with two different variables?)")
        segs = {1: [], 2: []}
        last = None
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) < 3 or line.startswith("#"):
                if last is not None:
                    segs[last].append((np.nan, np.nan))
                continue
            k = int(float(parts[2]))
            segs[k].append((float(parts[0]), float(parts[1])))
            last = k
        # XPP plot indices: 0 is t, 1.. are the columns after t
        xi = ctypes.c_int.in_dll(self._c, "null_ix").value
        yi = ctypes.c_int.in_dll(self._c, "null_iy").value
        names = self.columns
        return {names[xi]: np.array(segs[1] or np.empty((0, 2))),
                names[yi]: np.array(segs[2] or np.empty((0, 2)))}

    # ------------------------------------------------------------------
    # equilibria
    # ------------------------------------------------------------------
    def equilibrium(self, guess=None):
        """Newton's method from `guess` (dict or sequence; default: current
        initial conditions).  Returns an Equilibrium with eigenvalues.
        The non-interactive core of Sing pts > Go."""
        n = self._c.pyxpp_node()
        x = (ctypes.c_double * n)()
        if guess is None:
            for i in range(n):
                x[i] = self._last_ic[i]
        elif isinstance(guess, dict):
            g = {str(k).lower(): v for k, v in guess.items()}
            for i in range(n):
                x[i] = g.get(self.vars[i].lower(), self._last_ic[i])
        else:
            for i, v in enumerate(guess):
                x[i] = v
        er, em, ierr = (ctypes.c_double * n)(), (ctypes.c_double * n)(), ctypes.c_int(0)
        self._run(self._c.pyxpp_equilibrium, x, er, em, ctypes.byref(ierr))
        if ierr.value != 0:
            raise XPPError(f"equilibrium not found (ierr={ierr.value})")
        ev = np.array([complex(er[i], em[i]) for i in range(n)])
        disc = ctypes.c_int.in_dll(self._c, "METHOD").value == 0
        return Equilibrium({self.vars[i]: x[i] for i in range(n)}, ev, discrete=disc)

    # ------------------------------------------------------------------
    def close(self):
        self._lib.close()

    def __repr__(self):
        return (f"<pyxpp.Model {self.path.name}: vars={self.vars} aux={self.aux} "
                f"pars={len(self.par_names)}>")


def method_key(value):
    v = str(value).strip().lower()
    if len(v) == 1 and v in _METHOD_KEYS:
        return v
    if v in _METHOD_ALIASES:
        return _METHOD_ALIASES[v]
    raise ValueError(f"unknown method {value!r}; choose from {sorted(_METHOD_ALIASES)}")


def load(path=None, **kw):
    """Load an .ode file.  See Model."""
    return Model(path, **kw)
