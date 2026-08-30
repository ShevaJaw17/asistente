# voz.py - Habla y escucha del asistente.
#  - Hablar: edge-tts sintetiza voz en español; se reproduce con winmm (Windows).
#  - Escuchar: micrófono via pyaudio + reconocimiento SpeechRecognition (Google).
import asyncio
import ctypes
import json
import os
import tempfile
import threading
import time

try:
    import edge_tts
except Exception:
    edge_tts = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyaudio
except Exception:
    pyaudio = None

# Voz configurable desde "voz_config.json" (voz, ritmo, tono, idioma STT).
_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CONFIG = os.path.join(_DIR, "voz_config.json")

_CONFIG = {}
try:
    with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
        _CONFIG = json.load(f)
except Exception:
    pass

VOZ = _CONFIG.get("voz", "es-MX-DaliaNeural")
RITMO = _CONFIG.get("ritmo", "-10%")
TONO = _CONFIG.get("tono", "+0Hz")
IDIOMA_STT = _CONFIG.get("idioma_stt", "es-MX")

_mutex = threading.Lock()


# ---------------------------- HABLAR (TTS) ----------------------------
def _sintetizar(texto, ruta):
    if edge_tts is None:
        raise RuntimeError("edge-tts no disponible")
    parametros = {}
    if RITMO:
        parametros["rate"] = RITMO
    if TONO and TONO != "+0Hz":
        parametros["pitch"] = TONO
    com = edge_tts.Communicate(texto, VOZ, **parametros)
    com.save_sync(ruta)


def _reproducir(ruta):
    mci = ctypes.windll.winmm.mciSendStringW
    alias = "asistente_tts"
    try:
        mci(f'open "{ruta}" type mpegvideo alias {alias}', None, 0, None)
        mci(f"play {alias} wait", None, 0, None)
    finally:
        try:
            mci(f"close {alias}", None, 0, None)
        except Exception:
            pass


def _existe_voz(texto):
    return bool(texto and texto.strip())


def hablar(texto, on_inicio=None, on_fin=None):
    """Habla `texto` en segundo plano (no bloquea la GUI).
    on_inicio / on_fin se llaman en el hilo de voz."""
    if not _existe_voz(texto):
        return
    with _mutex:
        if edge_tts is None:
            return

    def trabajo():
        if on_inicio:
            try:
                on_inicio()
            except Exception:
                pass
        fd, ruta = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            _sintetizar(texto, ruta)
            _reproducir(ruta)
        except Exception:
            pass
        finally:
            try:
                os.remove(ruta)
            except Exception:
                pass
        if on_fin:
            try:
                on_fin()
            except Exception:
                pass

    threading.Thread(target=trabajo, daemon=True).start()


def hablar_sincrono(texto):
    """Habla bloqueante (para pruebas/CLI)."""
    if not _existe_voz(texto):
        return
    with _mutex:
        if edge_tts is None:
            return
        fd, ruta = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            _sintetizar(texto, ruta)
            _reproducir(ruta)
        finally:
            try:
                os.remove(ruta)
            except Exception:
                pass


# ---------------------------- ESCUCHAR (STT) ----------------------------
def _grabar(duracion_max=8.0, silencio=1.0):
    """Graba con el micrófono y devuelve sr.AudioData."""
    if sr is None or pyaudio is None:
        raise RuntimeError("speech_recognition/pyaudio no disponible")
    r = sr.Recognizer()
    r.pause_threshold = silencio
    with sr.Microphone() as fuente:
        r.adjust_for_ambient_noise(fuente, duration=0.6)
        try:
            audio = r.listen(fuente, timeout=duracion_max, phrase_time_limit=duracion_max)
        except sr.WaitTimeoutError:
            raise TimeoutError("No se detectó voz a tiempo")
    return r, audio


def escuchar(duracion_max=8.0, silencio=1.0):
    """Escucha y devuelve (texto, error). texto="" si no entendió, error con descripción."""
    try:
        r, audio = _grabar(duracion_max, silencio)
    except TimeoutError:
        return "", "silencioso"
    except Exception as e:
        return "", f"micrófono: {e}"
    try:
        texto = r.recognize_google(audio, language=IDIOMA_STT)
        return texto, None
    except sr.RequestError as e:
        return "", f"sin servicio de reconocimiento: {e}"
    except sr.UnknownValueError:
        return "", "no se entendió"
    except Exception as e:
        return "", f"reconocimiento: {e}"


if __name__ == "__main__":
    print("Probando HABLA...")
    hablar_sincrono("Hola, soy Nico Robin. Ahora puedo hablar en voz alta.")
    time.sleep(1)
    print("Probando ESCUCHA (habla algo)...")
    texto, error = escuchar()
    if error:
        print("Error:", error)
    else:
        print("Oíste:", texto)