"""
Low-level access to the headless XPPAUT library.

Each Model gets its *own copy* of the shared library (copied to a temporary
file and dlopen'ed with RTLD_LOCAL).  XPP keeps all of its state in C
globals, so a private copy is what lets several models live in one Python
process without trampling each other.
"""
import contextlib
import ctypes
import ctypes.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LIBNAME = "_libxpp.dylib" if sys.platform == "darwin" else "_libxpp.so"
_LIBPATH = _HERE / _LIBNAME

_libc = ctypes.CDLL(ctypes.util.find_library("c"))
_libc.fflush.argtypes = [ctypes.c_void_p]

c_int, c_double, c_char_p = ctypes.c_int, ctypes.c_double, ctypes.c_char_p
P_int = ctypes.POINTER(c_int)
P_double = ctypes.POINTER(c_double)

_PROTOS = {
    "pyxpp_error": (c_char_p, []),
    "pyxpp_init": (c_int, [c_int, ctypes.POINTER(c_char_p), c_char_p]),
    "pyxpp_set_log": (c_int, [c_char_p]),
    "pyxpp_flush_log": (None, []),
    "pyxpp_tape_clear": (None, []),
    "pyxpp_tape_push": (c_int, [c_char_p]),
    "pyxpp_tape_len": (c_int, []),
    "pyxpp_transcript": (c_char_p, []),
    "pyxpp_transcript_clear": (None, []),
    "pyxpp_key": (c_int, [c_int]),
    "pyxpp_command": (c_int, [c_int]),
    "pyxpp_num_key": (c_int, [c_int]),
    "pyxpp_menu_state": (c_int, []),
    "pyxpp_main_menu": (c_int, []),
    "pyxpp_auto_key": (c_int, [c_int]),
    "pyxpp_auto_open": (c_int, []),
    "pyxpp_set_option": (c_int, [c_char_p, c_char_p]),
    "pyxpp_get_val": (c_int, [c_char_p, P_double]),
    "pyxpp_set_val": (c_int, [c_char_p, c_double]),
    "pyxpp_equilibrium": (c_int, [P_double, P_double, P_double, P_int]),
    "pyxpp_node": (c_int, []),
    "pyxpp_neq": (c_int, []),
    "pyxpp_nmarkov": (c_int, []),
    "pyxpp_npar": (c_int, []),
    "pyxpp_var_name": (c_char_p, [c_int]),
    "pyxpp_par_name": (c_char_p, [c_int]),
    "pyxpp_data_rows": (c_int, []),
    "pyxpp_data_cols": (c_int, []),
    "pyxpp_data_copy": (None, [P_double]),
    "pyxpp_diag_count": (c_int, []),
    "pyxpp_diag_get": (c_int, [c_int, P_int, P_double, P_double]),
    "pyxpp_auto_par_index": (c_int, [c_int]),
    "pyxpp_n_auto_par": (c_int, []),
    "pyxpp_auto_settings": (None, [P_int, P_double]),
    "pyxpp_auto_par_name": (c_char_p, [c_int]),
    "pyxpp_set_auto_dir": (None, [c_char_p]),
    "pyxpp_real_to_pixel": (None, [c_double, c_double, P_int, P_int]),
}


class XPPError(RuntimeError):
    """An XPP command failed, needed input that was not supplied, or tried
    to do something that has no headless equivalent."""


def library_path() -> Path:
    if not _LIBPATH.exists():
        raise ImportError(
            f"{_LIBPATH} not found. Build it with:  python build_lib.py")
    return _LIBPATH


class Lib:
    """A private instance of libxpp plus a scratch directory."""

    def __init__(self, workdir: Path):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._copy = self.workdir / f"libxpp_{os.getpid()}_{id(self)}{_LIBPATH.suffix}"
        shutil.copyfile(library_path(), self._copy)
        mode = getattr(os, "RTLD_LOCAL", 0) | getattr(os, "RTLD_NOW", 2)
        self.c = ctypes.CDLL(str(self._copy), mode=mode)
        for name, (res, args) in _PROTOS.items():
            f = getattr(self.c, name)
            f.restype = res
            f.argtypes = args
        self.logpath = self.workdir / "xpp.log"

    # -- stdout capture -------------------------------------------------
    @contextlib.contextmanager
    def captured(self, enabled=True):
        """Send C-level stdout (XPP and AUTO print with printf) to the log
        file for the duration of a call."""
        if not enabled:
            yield
            return
        sys.stdout.flush()
        _libc.fflush(None)
        saved = os.dup(1)
        fd = os.open(self.logpath, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.dup2(fd, 1)
            yield
        finally:
            _libc.fflush(None)
            os.dup2(saved, 1)
            os.close(saved)
            os.close(fd)

    def check(self, rc):
        if rc != 0:
            raise XPPError(self.c.pyxpp_error().decode(errors="replace"))
        return rc

    def tape(self, answers):
        self.c.pyxpp_tape_clear()
        for a in answers:
            if not isinstance(a, (str, bytes)):
                a = format_answer(a)
            if isinstance(a, str):
                a = a.encode()
            if self.c.pyxpp_tape_push(a) != 0:
                raise XPPError("too many answers")

    def leftover(self):
        return self.c.pyxpp_tape_len()

    def close(self):
        try:
            os.unlink(self._copy)
        except OSError:
            pass


def format_answer(a):
    """Turn a Python value into the text XPP would have been typed."""
    if isinstance(a, bool):
        return "y" if a else "n"
    if isinstance(a, float):
        return repr(a)
    if isinstance(a, dict):
        return ";".join(f"{k}={format_answer(v)}" for k, v in a.items())
    if isinstance(a, (list, tuple)):
        return ",".join(format_answer(v) for v in a)
    return str(a)


ESC = "\x1b"


def new_workdir(prefix="pyxpp_"):
    return Path(tempfile.mkdtemp(prefix=prefix))
