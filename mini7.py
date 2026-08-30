import ctypes
import os
import threading
import time
import tkinter as tk

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "mini7.log")

user32 = ctypes.windll.user32


def fg_title():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def hb():
    n = 0
    while True:
        time.sleep(2)
        n += 1
        try:
            with open(LOG, "a") as f:
                f.write("hb %d %s fg=[%s]\n" % (n, time.strftime("%H:%M:%S"), fg_title()))
        except Exception:
            pass
        if n >= 165:
            try:
                with open(LOG, "a") as f:
                    f.write("OK 5.5min sin cerrarse (n=%d)\n" % n)
            except Exception:
                pass
            os._exit(0)


threading.Thread(target=hb, daemon=True).start()

r = tk.Tk()
r.title("Asistente Virtual Local")
r.geometry("640x480")
r.attributes("-topmost", True)

with open(LOG, "a") as f:
    f.write("antes mainloop %s\n" % time.strftime("%H:%M:%S"))
r.mainloop()
with open(LOG, "a") as f:
    f.write("DESPUES mainloop %s\n" % time.strftime("%H:%M:%S"))
with open(LOG, "a") as f:
    f.write("fg al morir=[%s]\n" % fg_title())