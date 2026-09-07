# Control de música: envía teclas multimedia del sistema (play, next, previous...)
# Funciona con cualquier reproductor que responda a media keys (Spotify, MPC, mpv...).
import tools.registro as reg

_PLAY_PAUSE = 0xB3
_NEXT = 0xB0
_PREV = 0xB1
_STOP = 0xB2
_VOL_UP = 0xAF
_VOL_DOWN = 0xAE
_MUTE = 0xAD

ACCIONES = {
    "play_pause": _PLAY_PAUSE,
    "reproducir": _PLAY_PAUSE,
    "pausar": _PLAY_PAUSE,
    "siguiente": _NEXT,
    "anterior": _PREV,
    "previous": _PREV,
    "stop": _STOP,
    "detener": _STOP,
    "volume_up": _VOL_UP,
    "subir_volumen": _VOL_UP,
    "volume_down": _VOL_DOWN,
    "bajar_volumen": _VOL_DOWN,
    "mute": _MUTE,
    "silenciar": _MUTE,
}


def _enviar_tecla(vk):
    import ctypes
    import ctypes.wintypes as wt

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD),
                    ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("union", INPUT_UNION)]

    def _press(vk_code):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki.wVk = vk_code
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        inp2 = INPUT(type=INPUT_KEYBOARD)
        inp2.union.ki.wVk = vk_code
        inp2.union.ki.dwFlags = KEYEVENTF_KEYUP
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp2), ctypes.sizeof(INPUT))

    _press(vk)


@reg.registrar(
    "controlar_musica",
    descripcion=(
        "Envía una acción de control multimedia al reproductor activo (Spotify, "
        "MPC, mpv, etc.). Funciona con cualquier app que responda a teclas media "
        "de Windows (F8, etc.). Acciones disponibles: play_pause (reproducir/"
        "pausar), siguiente (next), anterior (previous), stop (detener), "
        "volume_up/subir_volumen, volume_down/bajar_volumen, mute/silenciar."
    ),
    parametros={
        "accion": {"type": "string", "description": "Acción a ejecutar: play_pause, siguiente, anterior, stop, volume_up, volume_down o mute.", "requerido": True},
    },
)
def controlar_musica(accion):
    accion = (accion or "").strip().lower().replace(" ", "_").replace("á", "a").replace("ó", "o")
    vk = ACCIONES.get(accion)
    if vk is None:
        return ("Acción no reconocida. Usa: play_pause (reproducir/pausar), "
                "siguiente, anterior, stop, volume_up, volume_down o mute.")
    try:
        _enviar_tecla(vk)
    except Exception as e:
        return f"No se pudo enviar la tecla multimedia: {e}"
    return f"Acción '{accion}' enviada al reproductor."  