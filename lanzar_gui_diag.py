import ctypes
import os
import sys
import threading
import time
import traceback

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "diag_crash.log")
HB = os.path.join(DIR, "diag_heartbeat.log")

import faulthandler

try:
    faulthandler.enable(open(os.path.join(DIR, "diag_fault.log"), "w"))
except Exception:
    pass

EXCEPTION_CONTINUE_EXECUTION = 0
EXCEPTION_CONTINUE_SEARCH = 1


def _dump_crash(exception_info):
    try:
        code = ctypes.c_ulong.from_address(exception_info).value
        if code != 0x80000003 and code != 0xC0000005:
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

os.chdir(DIR)


def _finalizacion():
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("======= atexit a las %s (pid=%d) =======\n" % (
            time.strftime("%H:%M:%S"), os.getpid()))
    sys.stdout.flush()
    sys.stderr.flush()


import atexit
atexit.register(_finalizacion)

import interfaz

_or = None
_real_destroy = None
_real_quit = None


def _traza_destroy(*a, **k):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(">>> root.destroy llamado desde:\n")
        f.write("".join(traceback.format_stack()[-14:]) + "\n")
    return _real_destroy(*a, **k)


def _traza_quit(*a, **k):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(">>> root.quit llamado desde:\n")
        f.write("".join(traceback.format_stack()[-14:]) + "\n")
    return _real_quit(*a, **k)


def _traza_mainloop(*a, **k):
    try:
        r = interfaz.main.module_mainloop(*a, **k)
    except BaseException:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("!!! mainloop lanzó excepción:\n")
            f.write(traceback.format_exc() + "\n")
        raise
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(">>> mainloop RETORNÓ a las %s\n" % time.strftime("%H:%M:%S"))
    return r


def _main_modificado():
    import tkinter as tk
    import tkinter.ttk as _ttk
    import interfaz as m

    _W = tk.Widget

    def _patr_destroy(real):
        def w(*a, **k):
            try:
                self = a[0] if a else (k.get("self") or "?")
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(">>> destroy(%r) de %s:\n" % (
                        self, type(self).__name__))
                    f.write("".join(traceback.format_stack()[-16:]) + "\n")
            except Exception:
                pass
            return real(*a, **k)
        return w

    for cls in (tk.Tk, tk.Toplevel, tk.Widget):
        try:
            cls.destroy = _patr_destroy(cls.destroy)
        except Exception:
            pass

    _tk = tk
    m._bloquear_instancia()
    root = _tk.Tk()
    root.title("Asistente Virtual Local")
    root.geometry("720x640")
    import tkinter as tk2
    m.AsistenteApp(root)
    try:
        root.lift()
        root.attributes("-topmost", True)
        root.after(800, lambda: root.attributes("-topmost", False))
    except Exception:
        pass
    t0 = time.time()
    pasos = 0
    while True:
        try:
            raiz_viva = root.winfo_exists()
        except Exception:
            raiz_viva = 0
        if not raiz_viva:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(">>> winfo_exists()=0 a los %.1fs (pasos=%d) %s\n" % (
                    time.time() - t0, pasos, time.strftime("%H:%M:%S")))
            break
        try:
            root.update()
        except BaseException as e:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write("!!! root.update() lanzó %r a los %.1fs\n%s\n" % (
                    e, time.time() - t0, traceback.format_exc()))
            raise
        pasos += 1
        time.sleep(0.02)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(">>> bucle manual salió a los %.1fs (pasos=%d) %s\n" % (
            time.time() - t0, pasos, time.strftime("%H:%M:%S")))


try:
    _main_modificado()
except BaseException:
    traceback.print_exc()
    sys.stderr.flush()
    raise