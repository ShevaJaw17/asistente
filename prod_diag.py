import ctypes
import os
import sys
import threading
import time
import traceback
import faulthandler

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "prod_crash.log")
HB = os.path.join(DIR, "prod_heartbeat.log")

try:
    faulthandler.enable(open(os.path.join(DIR, "prod_fault.log"), "w"))
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
import interfaz

try:
    interfaz.main()
except BaseException:
    traceback.print_exc()
    try:
        sys.stderr.flush()
    except Exception:
        pass
    raise