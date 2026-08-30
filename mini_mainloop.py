import os
import sys
import threading
import time
import tkinter as tk

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "mini.log")


def hb():
    n = 0
    while True:
        time.sleep(3)
        n += 1
        try:
            with open(LOG, "a") as f:
                f.write("hb %d %s\n" % (n, time.strftime("%H:%M:%S")))
        except Exception:
            pass
        if n > 60:
            sys.exit(0)


threading.Thread(target=hb, daemon=True).start()

r = tk.Tk()
r.title("Mini prueba")
with open(LOG, "a") as f:
    f.write("antes de mainloop %s\n" % time.strftime("%H:%M:%S"))
r.mainloop()
with open(LOG, "a") as f:
    f.write("DESPUES de mainloop %s\n" % time.strftime("%H:%M:%S"))