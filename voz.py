# voz.py - Habla y escucha del asistente.
#  - Hablar: voz clonada de Robin (Chatterbox, local), Kokoro-82M (local) o
#    edge-tts (fallback) sintetizan la voz en español; se reproduce con winmm (Windows).
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

# Kokoro-82M (local, CPU). Se importa de forma perezosa y en un único pipeline.
_KOKORO = None
_KOKORO_PIPELINE = None
_KOKORO_SR = 24000


# --- Voz clonada de Robin (Chatterbox, Resemble AI, local, MIT) ---
# Usa un clip de referencia de la voz (data/robin_ref.wav) para clonar en cero-shots.
_VOZ_ROBIN = "robin"          # identificador con el que se selecciona esta voz.
_CHATTERBOX = None             # (modelo, sr) cargados de forma perezosa.


def _obtener_chatterbox():
    """Devuelve (modelo, sr) de Chatterbox cargados en CPU (una sola vez)."""
    global _CHATTERBOX
    if _CHATTERBOX is None:
        import torch
        import torchaudio  # noqa: F401  (lo necesita el motor)
        import perth
        # Chatterbox rompe la carga en CPU sin CUDA: el watermarker real es None.
        perth.PerthImplicitWatermarker = perth.DummyWatermarker
        from chatterbox import ChatterboxMultilingualTTS
        modelo = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
        _CHATTERBOX = (modelo, modelo.sr)
    return _CHATTERBOX


def _es_voz_robin(voz):
    """True si la voz seleccionada es la clonada de Robin (Chatterbox)."""
    return bool(voz) and voz.strip().lower() == _VOZ_ROBIN


def _ruta_referencia():
    return os.path.join(_DIR, "data", "robin_ref.wav")


def _sintetizar_chatterbox(texto, ruta):
    """Sintetiza `texto` con la voz clonada de Robin y lo guarda en `ruta` (.wav)."""
    modelo, sr = _obtener_chatterbox()
    wav = modelo.generate(
        text=texto,
        language_id="es",
        audio_prompt_path=_ruta_referencia(),
        temperature=0.8,
        repetition_penalty=2.0,
        min_p=0.05,
        top_p=1.0,
    )
    wav = wav.squeeze(0).cpu()
    import torchaudio
    torchaudio.save(ruta, wav.unsqueeze(0), sr, encoding="PCM_S", bits_per_sample=16)


def _obtener_kokoro():
    """Devuelve (KPipeline, sf, np, sample_rate) para una voz de Kokoro como 'ef_dora'."""
    global _KOKORO, _KOKORO_PIPELINE, _KOKORO_SR
    if _KOKORO_PIPELINE is None:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
        _KOKORO = (KPipeline, sf, np)
        _KOKORO_PIPELINE = KPipeline(lang_code="e", repo_id="hexgrad/Kokoro-82M", device="cpu")
        _KOKORO_SR = 24000
    KPipeline, sf, np = _KOKORO
    return _KOKORO_PIPELINE, sf, np, _KOKORO_SR


def _es_voz_kokoro(voz):
    """True si `voz` es una voz local de Kokoro (prefijo 'ef_' o 'em_').
    Las de edge-tts llevan '.Neural' y la clonada de Robin se trata aparte."""
    v = (voz or "").strip().lower()
    return v[:3] in ("ef_", "em_")


def _es_voz_edge(voz):
    """True si `voz` es una voz online de edge-tts (contiene '.Neural')."""
    return bool(voz) and ".Neural" in voz


def _usa_wav(voz):
    """Las voces locales (Kokoro, Chatterbox) generan .wav; edge-tts genera .mp3."""
    return _es_voz_robin(voz) or _es_voz_kokoro(voz)

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
    if _es_voz_robin(VOZ):
        try:
            _sintetizar_chatterbox(texto, ruta)
        except Exception:
            if edge_tts is None:
                raise RuntimeError("no hay motor TTS disponible (chatterbox y edge-tts fallaron)")
            _sintetizar_edge(texto, ruta)
        return
    if _es_voz_kokoro(VOZ):
        try:
            KPipeline, sf, np, sr = _obtener_kokoro()
        except Exception:
            if edge_tts is None:
                raise RuntimeError("no hay motor TTS disponible (kokoro y edge-tts fallaron)")
            _sintetizar_edge(texto, ruta)
            return
        audios = []
        try:
            for res in KPipeline(texto, voice=VOZ, speed=1.0):
                audios.append(res.audio.numpy())
        except Exception:
            if edge_tts is not None:
                _sintetizar_edge(texto, ruta)
                return
            raise
        full = np.concatenate(audios) if audios else np.zeros(0, dtype=np.float32)
        sf.write(ruta, full, sr)
        return
    if edge_tts is None:
        raise RuntimeError("edge-tts no disponible")
    _sintetizar_edge(texto, ruta)


def _sintetizar_edge(texto, ruta, voz=None):
    voice = voz or ("es-MX-DaliaNeural"
                    if (_es_voz_kokoro(VOZ) or _es_voz_robin(VOZ)) else VOZ)
    parametros = {}
    if RITMO:
        parametros["rate"] = RITMO
    if TONO and TONO != "+0Hz":
        parametros["pitch"] = TONO
    com = edge_tts.Communicate(texto, voice, **parametros)
    com.save_sync(ruta)


def _formato_audio(ruta):
    """Detecta el formato real por la cabecera, no por la extensión.
    Devuelve el 'type' de MCI: 'waveaudio' para WAV, 'mpegvideo' para MP3."""
    try:
        with open(ruta, "rb") as f:
            cabeza = f.read(12)
        if cabeza[:4] == b"RIFF" and cabeza[8:12] == b"WAVE":
            return "waveaudio"
        return "mpegvideo"
    except Exception:
        return "waveaudio" if ruta.lower().endswith(".wav") else "mpegvideo"


def _reproducir(ruta):
    """Reproduce `ruta` (WAV o MP3). Para WAV usa winsound (muy fiable en
    Windows); para MP3 usa MCI. Lanza excepción si no se puede reproducir."""
    if _formato_audio(ruta) == "waveaudio":
        import winsound
        # winsound.PlaySound devuelve None en éxito y False si falla.
        ok = winsound.PlaySound(ruta, winsound.SND_FILENAME)
        if ok is False:
            raise RuntimeError("winsound no pudo reproducir el audio")
        return
    mci = ctypes.windll.winmm.mciSendStringW
    alias = "asistente_tts"
    mciopen = mci(f'open "{ruta}" type mpegvideo alias {alias}', None, 0, None)
    if mciopen != 0:
        raise RuntimeError(f"MCI no pudo abrir el audio: code {mciopen}")
    try:
        err = mci(f"play {alias} wait", None, 0, None)
        if err != 0:
            raise RuntimeError(f"MCI no pudo reproducir el audio: code {err}")
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
        if _es_voz_edge(VOZ) and edge_tts is None:
            return

    def trabajo():
        if on_inicio:
            try:
                on_inicio()
            except Exception:
                pass
        fd, ruta = tempfile.mkstemp(suffix=(".wav" if _usa_wav(VOZ) else ".mp3"))
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
        if _es_voz_edge(VOZ) and edge_tts is None:
            return
        fd, ruta = tempfile.mkstemp(suffix=(".wav" if _usa_wav(VOZ) else ".mp3"))
        os.close(fd)
        try:
            _sintetizar(texto, ruta)
            _reproducir(ruta)
        finally:
            try:
                os.remove(ruta)
            except Exception:
                pass


# ----------------- Voz por fragmentos (streaming TTS) -----------------
# Permite que el GUI vaya encolando frases a medida que el texto se genera:
# un hilo consumidor las sintetiza y reproduce en orden, en paralelo al avance
# del texto. Útil porque el TTS local (Chatterbox) es lento en CPU.
import queue as _queue

_COLA_VOZ = _queue.Queue()
_HILO_VOZ = None


def _consumir_voz():
    """Consume la cola de fragmentos indefinidamente: sintetiza + reproduce."""
    while True:
        try:
            texto = _COLA_VOZ.get()
            if texto is None:
                break
            if _existe_voz(texto):
                fd, ruta = tempfile.mkstemp(suffix=(".wav" if _usa_wav(VOZ) else ".mp3"))
                os.close(fd)
                try:
                    _sintetizar(texto, ruta)
                    _reproducir(ruta)
                finally:
                    try:
                        os.remove(ruta)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            _COLA_VOZ.task_done()


def _asegurar_hilo_voz():
    global _HILO_VOZ
    if _HILO_VOZ is None or not _HILO_VOZ.is_alive():
        _HILO_VOZ = threading.Thread(target=_consumir_voz, daemon=True)
        _HILO_VOZ.start()


def hablar_fragmento(texto):
    """Encola una frase para que suene apenas el TTS la procese (no bloquea).
    Los fragmentos se reproducen en orden en el hilo de voz."""
    if not _existe_voz(texto):
        return
    _asegurar_hilo_voz()
    _COLA_VOZ.put(texto)


def hablar_stream(fragmentos):
    """Encola una secuencia de fragmentos de texto (iterable) que suena en
    paralelo al avance del texto. Inicia el habla por streaming."""
    _asegurar_hilo_voz()
    for frag in fragmentos:
        if frag and frag.strip():
            _COLA_VOZ.put(frag)


def detener_voz():
    """Vacía la cola pendiente e interrumpe el audio en reproducción."""
    while not _COLA_VOZ.empty():
        try:
            _COLA_VOZ.get_nowait()
            _COLA_VOZ.task_done()
        except Exception:
            break
    try:
        ctypes.windll.winmm.mciSendStringW("close todos", None, 0, None)
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