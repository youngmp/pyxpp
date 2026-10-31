"""
pyxpp test suite.  Run:  python -m pytest tests -q

Reference values come from running the same .ode through the XPPAUT
command-line binary or from the GUI's AUTO window on the same settings.
"""
import warnings
from pathlib import Path

import numpy as np
import pytest

import pyxpp

HERE = Path(__file__).resolve().parent
LECAR = HERE.parent / "examples" / "lecar.ode"

VDP = """
x'=y
y'=-x+mu*(1-x^2)*y
par mu=1
init x=2,y=0
@ total=50,dt=0.01
done
"""


@pytest.fixture
def lecar():
    m = pyxpp.load(LECAR)
    yield m
    m.close()


def test_load_names(lecar):
    assert [v.lower() for v in lecar.vars] == ["v", "w"]
    assert [a.lower() for a in lecar.aux] == ["cur", "ica", "ik", "rate"]
    assert "iapp" in lecar.pars and lecar.pars["iapp"] == 0.0
    assert lecar.numerics["total"] == 30


def test_run_matches_cli_endpoint(lecar):
    tr = lecar.run()
    assert tr.array.shape == (601, 7)
    # equilibrium at iapp=0 (same as AUTO's EP below)
    assert tr["v"][-1] == pytest.approx(-0.4956167, abs=1e-6)


def test_set_params_and_options(lecar):
    lecar.set(iapp=0.1, total=100, dt=0.025, meth="rk4")
    assert lecar.numerics["total"] == 100
    assert lecar.numerics["dt"] == 0.025
    tr = lecar.run()
    assert len(tr) == 4001
    assert tr["v"].max() > 0.2          # oscillates at iapp=0.1


def test_equilibrium(lecar):
    eq = lecar.equilibrium({"v": -0.5, "w": 0})
    assert eq.stable
    assert eq.x["V"] == pytest.approx(-0.4956167, abs=1e-6)
    assert np.all(eq.eigenvalues.real < 0)


def test_buttons_and_transcript(lecar):
    lecar.buttons.numerics.dt(0.01)
    assert lecar.numerics["dt"] == 0.01
    assert "Delta t" in lecar.transcript
    lecar.buttons.numerics.method.cvode()
    assert lecar.numerics["meth"] == "cvode"
    lecar.buttons.parameters("iapp", 0.07, "")
    assert lecar.pars["iapp"] == 0.07


def test_unused_answers_warn(lecar):
    with pytest.warns(pyxpp.AnswersNotUsed):
        lecar.buttons.erase("not asked")


def test_bad_menu_answer(lecar):
    with pytest.raises(pyxpp.XPPError, match="no entry"):
        lecar.buttons.initialconds("zz")


def test_exit_does_not_kill_python(lecar):
    with pytest.raises(pyxpp.XPPError, match="exit"):
        lecar.buttons.file.quit(True)


def test_endless_loop_guard(lecar):
    with pytest.raises(pyxpp.XPPError, match="without an answer"):
        lecar.buttons.file.tutorial()


def test_bad_ode():
    with pytest.raises(pyxpp.XPPError):
        pyxpp.load(text="x'=y+\ndone\n")


def test_two_models_are_independent(lecar):
    m2 = pyxpp.load(text=VDP)
    lecar.pars["iapp"] = 0.05
    tr = m2.run()
    assert tr["x"].max() == pytest.approx(2.0, abs=0.05)
    assert lecar.pars["iapp"] == 0.05
    assert "mu" not in lecar.pars


def test_nullclines(lecar):
    nc = lecar.nullclines()
    assert set(nc) == {"V", "W"}
    assert all(len(a) > 50 for a in nc.values())


def test_auto_steady_state_and_hopf(lecar):
    lecar.run(total=200)
    lecar.run_last(total=10)
    a = lecar.auto
    br = a.run("iapp", start="steady", ds=0.01, dsmax=0.02, parmin=-0.2, parmax=0.5)
    types = [(p.type, round(p.x, 4)) for p in br.labeled()]
    assert ("LP", 0.0833) in types
    assert ("LP", -0.0207) in types
    assert ("HB", 0.2038) in types
    hb = br.special("HB")[0]
    po = a.run(grab=hb.label, choice="periodic", dsmax=0.05, nmax=400)
    assert all(p.periodic for p in po)
    # cycles fold at iapp ~ 0.242 (subcritical Hopf)
    assert any(p.type == "LP" and abs(p.x - 0.2420) < 1e-3 for p in po)
    assert len(a.diagram) == len(br) + len(po)


def test_auto_two_parameter_fold(lecar):
    lecar.run(total=200)
    lecar.run_last(total=10)
    a = lecar.auto
    a.run("iapp", start="steady", ds=0.01, dsmax=0.02, parmin=-0.2, parmax=0.5)
    two = a.run(grab=2, param2="gca", nmax=300, parmax=0.6)
    assert len(two) > 10 and all(p.two_par for p in two)


def test_every_button_is_callable_without_crashing():
    """Each button pressed with no answers in a fresh process (a crash in C
    would take the test runner down otherwise)."""
    import subprocess
    import sys
    from pyxpp.buttons import Menu

    m = pyxpp.load(LECAR)
    paths = []

    def walk(menu, prefix):
        for n in menu._children:
            b = getattr(menu, n)
            paths.append(prefix + [n])
            if isinstance(b, Menu):
                walk(b, prefix + [n])

    walk(m.buttons, ["buttons"])
    walk(m.auto.buttons, ["auto", "buttons"])
    child = (
        "import sys, warnings; warnings.simplefilter('ignore')\n"
        "import pyxpp\n"
        f"m = pyxpp.load({str(LECAR)!r})\n"
        "m.run(total=200); m.run_last(total=5)\n"
        "if sys.argv[1] == 'auto':\n"
        "    m.auto.run('iapp', start='steady')  # so AUTO buttons have a diagram\n"
        "b = m\n"
        "for p in sys.argv[1:]: b = getattr(b, p)\n"
        "try:\n"
        "    b()\n"
        "except pyxpp.XPPError:\n"
        "    pass\n"
        "print('DONE')\n")
    crashed = []
    for p in paths:
        r = subprocess.run([sys.executable, "-c", child, *p], capture_output=True,
                           text=True, timeout=120, cwd=str(HERE.parent))
        if "DONE" not in r.stdout:
            crashed.append((".".join(p), r.returncode, r.stderr[-300:]))
    assert not crashed, crashed
