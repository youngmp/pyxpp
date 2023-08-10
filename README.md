# pyxpp
XPP as a Python module

The Makefile has some minor changes:
* Uses gcc-9 explicitly
* LDFLAGS=-L/usr/include/X11 and -I/usr/include/X11 in CFLAGS
* $(CC2) used create the libxppAPI.so file.

Only tried compiling on Ubuntu 20.04.6

libxppAPI.so is the precompiled library. Makefile will overwrite this.

Run test_calls.py in xpp_source to check libxppAPI.so gets called correctly. Nothing should happen; if there are no segfaults you are in good shape.

Jupyter Lab is available on Conda if you want to run the notebooks.
