"""
Morris-Lecar: simulation, phase plane, and a one-parameter bifurcation
diagram in iapp, all through pyxpp.  Writes lecar_demo.png.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

import pyxpp

m = pyxpp.load(Path(__file__).with_name("lecar.ode"))

fig, ax = plt.subplots(1, 3, figsize=(13, 4))

# 1. voltage traces for three currents
for iapp, tr in zip((0.0, 0.07, 0.1), m.sweep("iapp", (0.0, 0.07, 0.1), total=200)):
    ax[0].plot(tr.t, tr["v"], label=f"iapp={iapp}")
ax[0].set(xlabel="t", ylabel="v")
ax[0].legend()

# 2. phase plane at iapp=0.1: nullclines and the limit cycle
m.pars["iapp"] = 0.1
tr = m.run(total=200)
nc = m.nullclines(x="v", y="w", xlo=-0.6, xhi=0.5, ylo=-0.1, yhi=0.6)
ax[1].plot(*nc["V"].T, "C1", label="v' = 0")
ax[1].plot(*nc["W"].T, "C2", label="w' = 0")
ax[1].plot(tr["v"], tr["w"], "k", lw=1)
ax[1].set(xlabel="v", ylabel="w")
ax[1].legend()

# 3. bifurcation diagram: equilibria in iapp, then the periodic branch from the Hopf
m.pars["iapp"] = 0.0
m.run(total=300)
m.run_last(total=10)                 # start AUTO on the equilibrium
br = m.auto.run("iapp", start="steady", ds=0.01, dsmax=0.02, parmin=-0.2, parmax=0.5)
hb = br.special("HB")[0]
m.auto.run(grab=hb.label, choice="periodic", dsmax=0.05, nmax=400)
m.auto.diagram.plot(y="v", ax=ax[2])

fig.tight_layout()
fig.savefig("lecar_demo.png", dpi=120)
print(m.auto.diagram)
