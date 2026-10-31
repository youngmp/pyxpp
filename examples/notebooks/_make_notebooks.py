"""Build the pyxpp example notebooks in examples/notebooks (run once, then execute)."""
from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)


def nb(cells):
    n = nbf.v4.new_notebook()
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    for kind, src in cells:
        src = src.strip("\n")
        n.cells.append(nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src))
    return n


md = lambda s: ("md", s)  # noqa: E731
py = lambda s: ("py", s)  # noqa: E731

# ---------------------------------------------------------------------------
run_sim = nb([
    md("""
# 1. Running simulations

Load an `.ode` file, change parameters and initial conditions, integrate, and get the data
browser back as a numpy array. No X11 window opens; XPP's terminal output goes to `m.log`.
"""),
    py("""
import numpy as np
import matplotlib.pyplot as plt
import pyxpp
"""),
    md("## Load a model"),
    py("""
m = pyxpp.load("../lecar.ode")
m
"""),
    py("""
print(m.vars)      # state variables
print(m.aux)       # aux quantities (also columns of the data)
print(m.pars)      # parameters, dict-like
print(m.ics)       # initial conditions, dict-like
"""),
    py("""
m.numerics         # @-options currently in effect
"""),
    md("## Integrate (Initialconds > Go)"),
    py("""
tr = m.run()
tr
"""),
    md("Columns are `t`, the variables, then the aux quantities. Names are case-insensitive."),
    py("""
fig, ax = plt.subplots(figsize=(6, 3))
ax.plot(tr.t, tr["v"], label="v")
ax.plot(tr.t, tr["w"], label="w")
ax.set_xlabel("t"); ax.legend();
"""),
    md("""
## Change parameters, initial conditions and numerics

`m.set` takes parameters, variables (initial conditions) and any `@` option from the .ode
syntax in one call. `run(**kw)` passes its keywords to `set` first.
"""),
    py("""
m.pars["iapp"] = 0.1
m.ics["v"] = -0.3
tr = m.run(total=200, dt=0.025, meth="rk4")
print(m.numerics["total"], m.numerics["dt"], m.numerics["meth"], len(tr))

fig, ax = plt.subplots(figsize=(6, 3))
ax.plot(tr.t, tr["v"])
ax.set_xlabel("t"); ax.set_ylabel("v");
"""),
    md("## Continue from where the last run stopped"),
    py("""
tr_next = m.run_last(total=50)       # Initialconds > Last
m.last_point()
"""),
    md("## Parameter sweeps"),
    py("""
runs = m.sweep("iapp", [0.0, 0.06, 0.08, 0.1], total=200)
fig, ax = plt.subplots(figsize=(6, 3))
for iapp, r in zip([0.0, 0.06, 0.08, 0.1], runs):
    ax.plot(r.t, r["v"], label=f"iapp={iapp}")
ax.legend(); ax.set_xlabel("t");
print("iapp restored to", m.pars["iapp"])
"""),
    md("## Data as pandas"),
    py("""
m.data.to_pandas().head()
"""),
    md("""
## Models from a string

Several models can be open at once; each runs in its own copy of the XPP library.
"""),
    py("""
vdp = pyxpp.load(text='''
x'=y
y'=-x+mu*(1-x^2)*y
par mu=1
init x=2,y=0
@ total=40,dt=0.01
done
''')
fig, ax = plt.subplots(figsize=(4, 4))
for mu in [0.5, 1, 3]:
    vdp.pars["mu"] = mu
    t = vdp.run()
    ax.plot(t["x"], t["y"], label=f"mu={mu}")
ax.set_xlabel("x"); ax.set_ylabel("y"); ax.legend();
"""),
    md("XPP's own messages:"),
    py("""
print(m.log[-500:])
"""),
])

# ---------------------------------------------------------------------------
buttons = nb([
    md("""
# 2. Every button as a Python call

`m.buttons` mirrors XPP's main window and `m.auto.buttons` the AUTO window, including the
keyboard shortcuts. Positional arguments answer whatever the button asks, in the order XPP
asks it:

| XPP asks for | pass |
|---|---|
| a value at a prompt | a number or string |
| a choice from a pop-up menu | the key letter or the entry label |
| a multi-field dialog | a dict `{field: value}` (unset fields keep their value) |
| a file name | a string |
| YES/NO | `True` / `False` |

Unanswered questions take XPP's default, as if Enter were pressed. `m.transcript` shows what
was asked during the last call.
"""),
    py("""
import pyxpp
m = pyxpp.load("../lecar.ode")
"""),
    md("## The button tree"),
    py("""
pyxpp.show(m.buttons)
"""),
    md("## Simple buttons"),
    py("""
m.buttons.initialconds.go()          # I G
print(len(m.data))
print(m.transcript)
"""),
    py("""
m.buttons.numerics.total(100)        # U T 100
print(m.transcript)
m.buttons.numerics.dt(0.02)          # U D 0.02
print(m.transcript)
m.numerics["total"], m.numerics["dt"]
"""),
    md("A submenu choice followed by prompts: Numerics > Method > CVODE asks for two tolerances and whether the system is banded."),
    py("""
m.buttons.numerics.method.cvode(1e-8, 1e-8)
print(m.transcript)
m.numerics["meth"], m.numerics["tol"]
"""),
    md("Parameters button: name, value, name, value, ..., then an empty name to stop."),
    py("""
m.buttons.parameters("iapp", 0.05, "gk", 1.8, "")
print(m.transcript)
m.pars["iapp"], m.pars["gk"]
"""),
    md("## Dialogs"),
    py("""
m.buttons.parameters("iapp", 0.1, "gk", 2.0, "")
m.buttons.numerics.method.runge_kutta()
m.buttons.initialconds.range({"Range over": "iapp", "Steps": 4,
                              "Start": 0.0, "End": 0.1,
                              "Reset storage": "N"})   # keep all 5 runs
print(m.transcript)
len(m.data)        # 5 runs stacked in the browser
"""),
    md("## Yes/no questions"),
    py("""
m.run(total=200, iapp=0)
m.buttons.sing_pts.go(True)          # "Print eigenvalues?" -> YES, "Draw strong sets?" -> default
print(m.transcript)
print(m.log[-400:])
"""),
    md("## Files"),
    py("""
m.buttons.file.write_set("lecar_run.set")        # File > Write set
m.buttons.graphic_stuff.svg("lecar.svg")        # XPP's own plot, drawn headless
import os; sorted(f for f in os.listdir(m.workdir) if not f.startswith("."))
"""),
    md("""
## Raw keys

`m.press(key, *answers)` presses one key in the main window: `m.press("i", "g")` is the same as
`m.buttons.initialconds.go()`.
"""),
    py("""
m.press("i", "g")
m.transcript
"""),
    md("## Mistakes are reported, not ignored"),
    py("""
try:
    m.buttons.initialconds("zz")
except pyxpp.XPPError as e:
    print(e)
"""),
    py("""
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    m.buttons.erase("nobody asked for this")
print(w[0].category.__name__)
"""),
    py("""
try:
    m.buttons.file.quit(True)      # XPP calls exit(); Python survives
except pyxpp.XPPError as e:
    print(e)
"""),
])

# ---------------------------------------------------------------------------
phase = nb([
    md("""
# 3. Phase plane

Nullclines, equilibria with eigenvalues, and trajectories for the Morris-Lecar model.
"""),
    py("""
import numpy as np
import matplotlib.pyplot as plt
import pyxpp
m = pyxpp.load("../lecar.ode")
"""),
    md("## Nullclines in a chosen window (Viewaxes > 2D, then Nullcline > New)"),
    py("""
nc = m.nullclines(x="v", y="w", xlo=-0.6, xhi=0.5, ylo=-0.1, yhi=0.6)
{k: v.shape for k, v in nc.items()}
"""),
    md("## Equilibria"),
    md("At `iapp=0` there are three equilibria. Newton's method from three guesses:"),
    py("""
eqs = [m.equilibrium({"v": v0, "w": w0}) for v0, w0 in [(-0.5, 0), (-0.08, 0.08), (0.0, 0.2)]]
for e in eqs:
    print(e, np.round(e.eigenvalues, 4))
"""),
    md("## Putting it together"),
    py("""
fig, ax = plt.subplots(figsize=(5, 5))
ax.plot(*nc["V"].T, color="C1", label="v' = 0")
ax.plot(*nc["W"].T, color="C2", label="w' = 0")
for v0 in [-0.3, -0.2, 0.0, 0.2]:
    tr = m.run(v=v0, w=0.0, total=100)
    ax.plot(tr["v"], tr["w"], "k", lw=0.8)
for e in eqs:
    ax.plot(e.x["V"], e.x["W"], "o", color="k", mfc="k" if e.stable else "w", ms=7)
ax.set(xlim=(-0.6, 0.5), ylim=(-0.1, 0.6), xlabel="v", ylabel="w"); ax.legend();
"""),
    md("## With applied current the middle branch loses its equilibria and a limit cycle appears"),
    py("""
m.pars["iapp"] = 0.1
nc = m.nullclines()
tr = m.run(v=0, w=0, total=200)
fig, ax = plt.subplots(figsize=(5, 5))
ax.plot(*nc["V"].T, color="C1", label="v' = 0")
ax.plot(*nc["W"].T, color="C2", label="w' = 0")
ax.plot(tr["v"], tr["w"], "k", lw=1)
ax.set(xlim=(-0.6, 0.5), ylim=(-0.1, 0.6), xlabel="v", ylabel="w"); ax.legend();
"""),
])

# ---------------------------------------------------------------------------
auto = nb([
    md("""
# 4. Bifurcation diagrams with AUTO

`m.auto.run` starts or continues a branch and returns the new points; `m.auto.diagram`
holds everything computed so far. AUTO's own table prints to `m.log`.
"""),
    py("""
import numpy as np
import matplotlib.pyplot as plt
import pyxpp
m = pyxpp.load("../lecar.ode")
"""),
    md("## Start on a stable equilibrium"),
    py("""
m.pars["iapp"] = 0.0
m.run(total=300)
m.run_last(total=10)
m.last_point()
"""),
    md("## Equilibria as `iapp` varies"),
    py("""
br = m.auto.run("iapp", start="steady",
                ds=0.01, dsmax=0.02, parmin=-0.2, parmax=0.5, nmax=2000)
br
"""),
    py("""
for p in br.labeled():
    print(f"{p.label:3d} {p.type:2s}  iapp={p.x:+.5f}  v={p.u0['v']:+.5f}  stable={p.stable}")
"""),
    md("## Periodic orbits from the Hopf point"),
    py("""
hb = br.special("HB")[0]
po = m.auto.run(grab=hb.label, choice="periodic", dsmax=0.05, nmax=400)
print(m.transcript)
po
"""),
    md("Points of a periodic branch store the max, min and average of each variable over the cycle, and the period."),
    py("""
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
m.auto.diagram.plot(y="v", ax=ax[0])
ax[1].plot([p.x for p in po], [p.period for p in po], ".")
ax[1].set(xlabel="iapp", ylabel="period", yscale="log");
"""),
    md("## The diagram as a table"),
    py("""
df = m.auto.diagram.to_pandas(y="v")
df[df.label > 0]
"""),
    md("## Two-parameter continuation of the fold"),
    py("""
lp = br.special("LP")[0]
two = m.auto.run(grab=lp.label, param2="gca", nmax=400, parmin=-0.2, parmax=0.6)
fig, ax = plt.subplots(figsize=(5, 4))
m.auto.diagram.plot(two_par=True, ax=ax)
ax.set_title("fold of equilibria in (iapp, gca)");
"""),
    md("## Settings, buttons and files"),
    py("""
s = m.auto.settings
{k: s[k] for k in ("param", "param2", "ntst", "nmax", "ds", "dsmax", "parmin", "parmax")}
"""),
    py("""
pyxpp.show(m.auto.buttons)
"""),
    py("""
m.auto.write_pts("lecar_bif.dat")      # File > Write pts
print(open(m.workdir / "lecar_bif.dat").read()[:300])
"""),
    md("AUTO's own output:"),
    py("""
types = {"EP", "LP", "HB", "BP", "PD", "TR", "MX", "UZ"}
rows = [l for l in m.log.splitlines()
        if "BR    PT" in l or (len(l.split()) > 3 and l.split()[2] in types)]
print("\\n".join(rows[:25]))
"""),
])

for name, n in [("01_run_sim", run_sim), ("02_buttons", buttons),
                ("03_phase_plane", phase), ("04_run_auto", auto)]:
    nbf.write(n, OUT / f"{name}.ipynb")
    print("wrote", name)
