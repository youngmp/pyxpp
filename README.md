# pyxpp


XPPAUT [10.1137/1.9780898718195] as a Python module. No X11: the GUI is gone, every
button is a Python call, and AUTO runs from Python.

```python
import pyxpp

m = pyxpp.load("examples/lecar.ode")
m.pars["iapp"] = 0.1
tr = m.run(total=200)                    # Initialconds > Go
tr["v"], tr.t, tr.to_pandas()

m.equilibrium({"v": -0.5, "w": 0})       # Newton + eigenvalues
m.nullclines()                           # {"V": (N,2), "W": (N,2)}

# AUTO
m.pars["iapp"] = 0; m.run(total=300); m.run_last(total=10)
br = m.auto.run("iapp", start="steady", ds=0.01, dsmax=0.02, parmin=-0.2, parmax=0.5)
hb = br.special("HB")[0]
po = m.auto.run(grab=hb.label, choice="periodic")
m.auto.diagram.plot(y="v")               # matplotlib
m.auto.diagram.to_pandas()
```

## Install

```
pip install .            # builds the C library; needs only a C compiler
python -m pytest tests   # 15 tests, ~30 s
```

No X11 headers or libraries are needed at build or run time (the few Xlib
headers XPP's sources include are vendored in `csrc/include`).

## Every button

`m.buttons` mirrors the XPP main window, `m.auto.buttons` the AUTO window.
`pyxpp.show(m.buttons)` prints the tree with keyboard shortcuts.

```python
m.buttons.initialconds.go()                      # I G
m.buttons.numerics.total(500)                    # U T 500
m.buttons.numerics.method.cvode(1e-8, 1e-8)      # U M C, answers both tolerance prompts
m.buttons.sing_pts.go(True)                      # S G, "Print eigenvalues?" -> yes
m.buttons.initialconds.range({"Range over": "iapp", "Steps": 10,
                              "Start": 0, "End": 0.2, "Reset storage": "N"})
m.buttons.graphic_stuff.svg("traj.svg")          # XPP's own plot, written headless
m.buttons.file.write_set("run1.set")
m.auto.buttons.file.write_pts("diagram.dat")
m.press("i", "g")                                # raw keys, same as the first line
```

Positional arguments answer whatever the button asks next, in order: a
prompt value, a menu choice (key letter or label), a multi-field dialog as a
dict, a file name, `True`/`False` for yes/no. Anything not supplied takes
XPP's default, as if Enter were pressed. After a call, `m.transcript` shows
each question and the answer used:

```
menu    Integrate -> (R)ange
field   Range Integrate.Range over = iapp (was V)
field   Range Integrate.Steps = 10 (was 20)
```

Use the transcript to discover what a button asks. Extra answers that were
never asked for raise an `AnswersNotUsed` warning.

## How it works

- `csrc/xppaut/` is the unmodified upstream source
  (github.com/Ermentrout/xppaut). `build_lib.py` copies it, applies the
  patches listed at the top of that file, and links `pyxpp/_libxpp.so`.
- `csrc/nox11.c` implements the ~70 Xlib calls XPP makes as no-ops, with a
  fake display, fonts and window geometry so XPP's layout code runs
  unchanged.
- `csrc/headless.c` replaces XPP's dialog primitives (`new_float`,
  `pop_up_list`, `two_choice`, `do_string_box`, `file_selector`, mouse
  clicks, the AUTO point browser, ...) with versions that read answers from a
  queue filled by Python. The menu handlers themselves are XPP's own code,
  so each button does exactly what it does in the GUI.
- `exit()` inside XPP raises `XPPError` instead of killing Python; an XPP
  loop that keeps asking with no answers raises after 500 questions.
- Each `Model` loads a private copy of the library, so several models can
  be open in one process (XPP keeps all state in C globals).

## Not available headless

- Buttons that only make sense with a live screen: Window > Scroll,
  AUTO Axes > Scroll, Viewaxes > Toon, Kinescope (captures blank frames).
  These raise `XPPError` or do nothing.
- Mouse buttons (Initialconds > Mouse, zoom boxes, text placement) take
  pixel answers `"ix,iy"` / `"x1,y1,x2,y2"`; there is no data-to-pixel
  helper in the Python API yet.
- `MAXSTOR` cannot be changed after loading.
- A segfault in XPP's C code still takes down the Python process (the full
  button sweep in the tests runs without one).

## License

GPL-2.0, as XPPAUT.
