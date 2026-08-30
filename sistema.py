# sistema.py - Automatización del sistema operativo Windows:
# volumen (API Core Audio por ctypes), captura de pantalla, limpieza de
# archivos temporales y papelera de reciclaje.
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
from ctypes import POINTER, byref, c_float, c_int, c_void_p, c_long, c_ubyte, Structure

WINFUNCTYPE = ctypes.WINFUNCTYPE
wintypes = wt

try:
    ole32 = ctypes.windll.ole32
    user32 = ctypes.windll.user32
except Exception:
    ole32 = None
    user32 = None

DIRECTORIO_PROYECTO = os.path.dirname(os.path.abspath(__file__))
CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"


class GUID(Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", c_ubyte * 8),
    ]


def _guid(s):
    limpio = s.strip("{}").replace("-", "")
    g = GUID()
    g.Data1 = int(limpio[0:8], 16)
    g.Data2 = int(limpio[8:12], 16)
    g.Data3 = int(limpio[12:16], 16)
    g.Data4 = (c_ubyte * 8)(*bytes.fromhex(limpio[16:32]))
    return g


def _vtable(obj):
    return ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents


def _llamar(obj, indice, *args, restype=c_long, argtypes=()):
    fn = ctypes.cast(
        _vtable(obj)[indice], WINFUNCTYPE(restype, c_void_p, *argtypes)
    )
    return fn(obj, *args)


def _crear_com(clsid, iid):
    if ole32 is not None:
        try:
            ole32.CoInitialize(None)
        except Exception:
            pass
        try:
            ole32.CoInitializeEx(None, 2)
        except Exception:
            pass
    obj = c_void_p()
    hr = ole32.CoCreateInstance(
        byref(_guid(clsid)), None, 1, byref(_guid(iid)), byref(obj)
    )
    if hr < 0 or not obj:
        raise OSError(f"CoCreateInstance falló (HRESULT {hr})")
    return obj


def esta_inicializado():
    return ole32 is not None


def obtener_volumen():
    """Devuelve el volumen maestro actual del sistema, de 0.0 a 1.0."""
    enumerador = _crear_com(CLSID_MMDeviceEnumerator, IID_IMMDeviceEnumerator)
    dispositivo = c_void_p()
    hr = _llamar(
        enumerador,
        4,
        0,
        0,
        byref(dispositivo),
        argtypes=(c_int, c_int, POINTER(c_void_p)),
    )
    if hr < 0 or not dispositivo:
        raise OSError(f"GetDefaultAudioEndpoint falló (HRESULT {hr})")
    volumen = c_void_p()
    hr = _llamar(
        dispositivo,
        3,
        byref(_guid(IID_IAudioEndpointVolume)),
        1,
        None,
        byref(volumen),
        argtypes=(POINTER(GUID), wt.DWORD, c_void_p, POINTER(c_void_p)),
    )
    if hr < 0 or not volumen:
        raise OSError(f"Activate IAudioEndpointVolume falló (HRESULT {hr})")
    nivel = c_float()
    hr = _llamar(volumen, 9, byref(nivel), argtypes=(POINTER(c_float),))
    if hr < 0:
        raise OSError(f"GetMasterVolumeLevelScalar falló (HRESULT {hr})")
    return max(0.0, min(1.0, nivel.value))


def ajustar_volumen(nivel):
    """Ajusta el volumen maestro del sistema (0-100). Devuelve un texto."""
    try:
        nivel = max(0, min(100, int(nivel)))
    except (TypeError, ValueError):
        return "Error: el volumen debe ser un número entre 0 y 100."
    try:
        enumerador = _crear_com(CLSID_MMDeviceEnumerator, IID_IMMDeviceEnumerator)
        dispositivo = c_void_p()
        hr = _llamar(
            enumerador,
            4,
            0,
            0,
            byref(dispositivo),
            argtypes=(c_int, c_int, POINTER(c_void_p)),
        )
        if hr < 0 or not dispositivo:
            raise OSError(f"GetDefaultAudioEndpoint falló (HRESULT {hr})")
        volumen = c_void_p()
        hr = _llamar(
            dispositivo,
            3,
            byref(_guid(IID_IAudioEndpointVolume)),
            1,
            None,
            byref(volumen),
            argtypes=(POINTER(GUID), wt.DWORD, c_void_p, POINTER(c_void_p)),
        )
        if hr < 0 or not volumen:
            raise OSError(f"Activate IAudioEndpointVolume falló (HRESULT {hr})")
        hr = _llamar(
            volumen,
            7,
            c_float(nivel / 100.0),
            None,
            argtypes=(c_float, c_void_p),
        )
        if hr < 0:
            raise OSError(f"SetMasterVolumeLevelScalar falló (HRESULT {hr})")
        real = obtener_volumen()
        return f"Volumen ajustado a {int(round(real * 100))}%."
    except Exception as e:
        return f"Error al ajustar el volumen: {e}"


def subir_bajar_volumen(porcentaje):
    """Sube o baja el volumen relativo (ej. -10 o +15). Devuelve un texto."""
    try:
        actual = obtener_volumen() * 100.0
        return ajustar_volumen(actual + float(porcentaje))
    except Exception as e:
        return f"Error al ajustar el volumen: {e}"


def capturar_pantalla():
    """Captura la pantalla completa y guarda una imagen PNG. Devuelve la ruta."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Error: falta la librería Pillow para capturar pantalla."
    try:
        from datetime import datetime

        carpeta = os.path.join(DIRECTORIO_PROYECTO, "capturas")
        os.makedirs(carpeta, exist_ok=True)
        imagen = ImageGrab.grab(all_screens=True)
        ruta = os.path.join(
            carpeta, f"captura_{datetime.now():%Y%m%d_%H%M%S}.png"
        )
        imagen.save(ruta)
        ancho, alto = imagen.size
        try:
            os.startfile(ruta)
        except Exception:
            pass
        return f"Captura de pantalla guardada y abierta: {ruta} ({ancho}x{alto} px)."
    except Exception as e:
        return f"Error al capturar la pantalla: {e}"


def limpiar_temporales(dias=7):
    """Elimina archivos temporales de %TEMP% más antiguos que 'dias' días."""
    try:
        dias = max(0, int(dias))
    except (TypeError, ValueError):
        return "Error: 'dias' debe ser un número."
    import time

    umbral = time.time() - dias * 86400
    carpetas = {
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
    }
    carpetas.discard(None)
    carpetas.discard("")
    borrados = 0
    bytes_liberados = 0
    errores = 0
    for carpeta in carpetas:
        if not carpeta or not os.path.isdir(carpeta):
            continue
        for raiz, _dirs, archivos in os.walk(carpeta):
            for nombre in archivos:
                ruta = os.path.join(raiz, nombre)
                try:
                    info = os.stat(ruta)
                    if info.st_mtime < umbral:
                        os.remove(ruta)
                        borrados += 1
                        bytes_liberados += info.st_size
                except OSError:
                    errores += 1
    parte = (
        f"Se eliminaron {borrados} archivos temporales "
        f"({bytes_liberados / 1048576:.1f} MB liberados)."
        if borrados
        else "No había archivos temporales antiguos que eliminar."
    )
    if errores:
        parte += f" ({errores} archivos en uso o bloqueados se omitieron)."
    return parte


def vaciar_papelera():
    """Vacia la papelera de reciclaje del sistema. Requiere deseo previo del usuario."""
    try:
        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Clear-RecycleBin -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
        )
        if resultado.returncode == 0:
            return "La papelera de reciclaje ha sido vaciada."
        return (
            "Se intentó vaciar la papelera pero hubo un problema: "
            + (resultado.stderr.strip() or resultado.stdout.strip() or "código 1")
        )
    except Exception as e:
        return f"Error al vaciar la papelera: {e}"