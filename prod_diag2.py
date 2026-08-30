import ctypes
import os
import sys
import threading
import time
import traceback
import faulthandler

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "diag2_crash.log")
HB = os.path.join(DIR, "diag2_heartbeat.log")

try:
    faulthandler.enable(open(os.path.join(DIR, "diag2_fault.log"), "w"))
except Exception:
    pass

EXCEPTION_CONTINUE_EXECUTION = 0
EXCEPTION_CONTINUE_SEARCH = 1


def _dump_crash(exception_info):
    try:
        code = ctypes.c_ulong.from_address(exception_info).value
        if code not in (0x80000003, 0xC0000005, 0xC0000409):
            return EXCEPTION_CONTINUE_SEARCH
        lines = []
        lines.append("======= EXCEPTION 0x%08X at %s (pid=%d) =======" % (
            code, time.strftime("%H:%M:%S"), os.getpid()))
        for tid, frame in sys._current_frames().items():
            cur = threading.main_thread().ident
            header = "--- MAIN THREAD %s ---" % tid if tid == cur else "--- THREAD %s ---" % tid
            lines.append(header)
            lines.append("".join(traceback.format_stack(frame)))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    return EXCEPTION_CONTINUE_EXECUTION


VEH_PROTO = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_ulonglong)
_veh = VEH_PROTO(_dump_crash)
try:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.AddVectoredExceptionHandler(1, _veh)
except Exception:
    pass


def _heartbeat():
    while True:
        time.sleep(5)
        try:
            live = []
            for tid, frame in sys._current_frames().items():
                live.append("T%s:%s" % (tid, frame.f_code.co_name))
            with open(HB, "a", encoding="utf-8") as f:
                f.write("%s pid=%d %s\n" % (
                    time.strftime("%H:%M:%S"), os.getpid(), " | ".join(live)))
        except Exception:
            pass


try:
    threading.Thread(target=_heartbeat, daemon=True).start()
except Exception:
    pass

import atexit


def _fin():
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("======= atexit %s pid=%d =======\n" % (
                time.strftime("%H:%M:%S"), os.getpid()))
    except Exception:
        pass
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass


atexit.register(_fin)

os.chdir(DIR)

import tkinter as tk
import interfaz

_orig_tk_init = tk.Tk.__init__
_orig_misc_init = tk.Misc.__init__


def _log(line):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _on_wm_delete(root):
    _log(">>> WM_DELETE_WINDOW recibido en root %r a las %s\n" % (
        root, time.strftime("%H:%M:%S")))
    try:
        root.destroy()
    except Exception:
        pass


def _report(exc, val, tb):
    _log("=== Tk callback exception ===\n%s\n" % "".join(
        traceback.format_exception(exc, val, tb)))
    _log("stacks:\n")
    for tid, frame in sys._current_frames().items():
        _log("%s\n%s\n" % (tid, "".join(traceback.format_stack(frame))))


def _tk_init(self, *a, **k):
    _orig_tk_init(self, *a, **k)
    try:
        self.report_callback_exception = _report
        self.protocol("WM_DELETE_WINDOW", lambda: _on_wm_delete(self))
    except Exception:
        pass


def _misc_init(self, *a, **k):
    _orig_misc_init(self, *a, **k)
    try:
        if isinstance(self, tk.Toplevel):
            self.protocol("WM_DELETE_WINDOW", lambda: _on_wm_delete(self))
            try:
                self.report_callback_exception = _report
            except Exception:
                pass
    except Exception:
        pass


try:
    tk.Tk.__init__ = _tk_init
    tk.Misc.__init__ = _misc_init
except Exception:
    pass

try:
    interfaz.main()
except BaseException:
    traceback.print_exc()
    try:
        sys.stderr.flush()
    except Exception:
        pass
    raise