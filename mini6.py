import os
import threading
import time
import tkinter as tk

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "mini6.log")


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
            try:
                with open(LOG, "a") as f:
                    f.write("SOBREVIVIO 60s\n")
            except Exception:
                pass
            os._exit(0)


threading.Thread(target=hb, daemon=True).start()

r = tk.Tk()
r.title("Mini prueba")
r.geometry("720x640")
r.minsize(560, 480)
with open(LOG, "a") as f:
    f.write("antes mainloop (tituloB, con geometry) %s\n" % time.strftime("%H:%M:%S"))
r.mainloop()
with open(LOG, "a") as f:
    f.write("DESPUES mainloop %s\n" % time.strftime("%H:%M:%S"))