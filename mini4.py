import os
import socket
import threading
import time
import tkinter as tk

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "mini4.log")


def lock():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 57777))
        s.listen(1)
        return True
    except OSError:
        return False


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

with open(LOG, "a") as f:
    f.write("lock=%s %s\n" % (lock(), time.strftime("%H:%M:%S")))

r = tk.Tk()
r.title("Asistente Virtual Local")
r.geometry("720x640")
r.minsize(560, 480)
# SIN lift, SIN -topmost


def on_wm_delete():
    with open(LOG, "a") as f:
        f.write("WM_DELETE_WINDOW %s\n" % time.strftime("%H:%M:%S"))
    r.destroy()


r.protocol("WM_DELETE_WINDOW", on_wm_delete)
with open(LOG, "a") as f:
    f.write("antes mainloop (sin topmost) %s\n" % time.strftime("%H:%M:%S"))
r.mainloop()
with open(LOG, "a") as f:
    f.write("DESPUES mainloop %s\n" % time.strftime("%H:%M:%S"))