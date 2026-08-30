import os
import threading
import time
import tkinter as tk

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "mini3.log")


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


threading.Thread(target=hb, daemon=True).start()

r = tk.Tk()
r.title("Asistente Virtual Local")
r.geometry("720x640")
r.minsize(560, 480)
r.lift()
r.attributes("-topmost", True)
r.after(800, lambda: r.attributes("-topmost", False))


def on_wm_delete():
    with open(LOG, "a") as f:
        f.write("WM_DELETE_WINDOW %s\n" % time.strftime("%H:%M:%S"))
    r.destroy()


r.protocol("WM_DELETE_WINDOW", on_wm_delete)
with open(LOG, "a") as f:
    f.write("antes mainloop (sin puerto) %s\n" % time.strftime("%H:%M:%S"))
r.mainloop()
with open(LOG, "a") as f:
    f.write("DESPUES mainloop %s\n" % time.strftime("%H:%M:%S"))