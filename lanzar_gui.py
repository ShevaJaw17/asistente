import faulthandler
import os
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gui_run.log"
)

try:
    log = open(LOG, "w", encoding="utf-8", buffering=1)
except Exception:
    log = None

if log is not None:
    sys.stdout = log
    sys.stderr = log

try:
    faulthandler.enable(log)
except Exception:
    pass

try:
    import interfaz

    interfaz.main()
except BaseException:
    traceback.print_exc()
    if log is not None:
        log.flush()