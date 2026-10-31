/* force.h -- included first in every XPP translation unit (-include).
 *
 * XPP calls exit() on parse errors and from "File > Quit".  Inside Python
 * that would kill the interpreter, so every call is rerouted to
 * pyxpp_exit(), which unwinds to the Python entry point with an error.
 * A macro (rather than a linker --wrap) keeps this portable to macOS ld64.
 */
#ifndef PYXPP_FORCE_H
#define PYXPP_FORCE_H
void pyxpp_exit(int code);
#define exit(c) pyxpp_exit(c)
#endif
