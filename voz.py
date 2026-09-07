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
    """Sintetiza `texto` con la voz clonada de Robin y lo guarda en `ruta` (.wav).
    Parámetros configurables en voz_config.json (chatterbox_temperature, ...):
    bajas temperaturas/top_p = voz más estable en frases largas."""
    modelo, sr = _obtener_chatterbox()
    wav = modelo.generate(
        text=texto,
        language_id="es",
        audio_prompt_path=_ruta_referencia(),
        temperature=CHATTERBOX_TEMPERATURE,
        repetition_penalty=CHATTERBOX_REPETITION,
        min_p=CHATTERBOX_MIN_P,
        top_p=CHATTERBOX_TOP_P,
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
# Grabación por voz: duración máx. de instrucción y pausa que cierra la frase.
DURACION_MAX = _CONFIG.get("duracion_max", 20.0)
SILENCIO = _CONFIG.get("silencio", 1.8)
# Motor STT: "auto" usa Vosk local si está disponible (sin internet), sino Google.
# También se puede forzar "vosk" o "google" desde voz_config.json.
MOTOR_STT = _CONFIG.get("motor_stt", "auto")
# Parámetros de síntesis de Chatterbox (voz clonada): valores más bajos de
# temperature / top_p hacen la voz más estable en frases largas.
CHATTERBOX_TEMPERATURE = _CONFIG.get("chatterbox_temperature", 0.6)
CHATTERBOX_REPETITION = _CONFIG.get("chatterbox_repetition", 2.2)
CHATTERBOX_TOP_P = _CONFIG.get("chatterbox_top_p", 0.9)
CHATTERBOX_MIN_P = _CONFIG.get("chatterbox_min_p", 0.05)

_lock_config = threading.Lock()


def _recargar_config():
    """Relee voz_config.json y refleja los cambios en las variables de módulo
    (permite cambiar voz/dictado/motor en vivo sin reiniciar)."""
    global VOZ, RITMO, TONO, IDIOMA_STT, DURACION_MAX, SILENCIO, MOTOR_STT
    global CHATTERBOX_TEMPERATURE, CHATTERBOX_REPETITION, CHATTERBOX_TOP_P, CHATTERBOX_MIN_P
    global _CONFIG
    nuevo = {}
    try:
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            nuevo = json.load(f)
    except Exception:
        return False
    with _lock_config:
        _CONFIG = nuevo
        VOZ = nuevo.get("voz", VOZ)
        RITMO = nuevo.get("ritmo", RITMO)
        TONO = nuevo.get("tono", TONO)
        IDIOMA_STT = nuevo.get("idioma_stt", IDIOMA_STT)
        DURACION_MAX = nuevo.get("duracion_max", DURACION_MAX)
        SILENCIO = nuevo.get("silencio", SILENCIO)
        MOTOR_STT = nuevo.get("motor_stt", MOTOR_STT)
        CHATTERBOX_TEMPERATURE = nuevo.get("chatterbox_temperature", CHATTERBOX_TEMPERATURE)
        CHATTERBOX_REPETITION = nuevo.get("chatterbox_repetition", CHATTERBOX_REPETITION)
        CHATTERBOX_TOP_P = nuevo.get("chatterbox_top_p", CHATTERBOX_TOP_P)
        CHATTERBOX_MIN_P = nuevo.get("chatterbox_min_p", CHATTERBOX_MIN_P)
    return True


def aplicar_config(cambios):
    """Aplica cambios a voz_config.json (en vivo) y refresca el módulo.
    `cambios` es dict de claves conocidas. Devuelve True si hubo cambio."""
    with _lock_config:
        nuevo = dict(_CONFIG)
        for k, v in (cambios or {}).items():
            if v is not None:
                nuevo[k] = v
    try:
        with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(nuevo, f, ensure_ascii=False, indent=2)
    except Exception:
        return False
    return _recargar_config()

# Cache de TTS: guarda el audio sintetizado por hash del texto en data/cache_voz/.
# Las frases frecuentes (saludos, ack) no se vuelven a sintetizar en CPU.
DIR_CACHE_VOZ = os.path.join(_DIR, "data", "cache_voz")

# Tamaño máximo del caché (número de archivos). A partir de ese límite se
# elimina el archivo más antiguo al escribir uno nuevo (mantiene acotado).
_CACHE_LIMITE = 200


def _clave_cache(texto):
    import hashlib
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


def _ruta_cache(texto):
    ext = ".wav" if _usa_wav(VOZ) else ".mp3"
    return os.path.join(DIR_CACHE_VOZ, _clave_cache(texto) + ext)


def _sintetizar_con_cache(texto):
    """Sintetiza `texto` y devuelve la ruta del audio (cacheado en disco).
    Si el texto ya fue sintetizado, no regraba; reutiliza el WAV/MP3."""
    try:
        os.makedirs(DIR_CACHE_VOZ, exist_ok=True)
    except Exception:
        pass
    ruta = _ruta_cache(texto)
    if os.path.exists(ruta) and os.path.getsize(ruta) > 0:
        return ruta
    fd, ruta_temp = tempfile.mkstemp(suffix=(".wav" if _usa_wav(VOZ) else ".mp3"))
    os.close(fd)
    _sintetizar(texto, ruta_temp)
    try:
        os.replace(ruta_temp, ruta)
    except Exception:
        os.remove(ruta_temp)
        raise
    _purgar_cache_si_procede()
    return ruta


def _purgar_cache_si_procede():
    """Si el caché excede _CACHE_LIMITE archivos, borra los más antiguos."""
    try:
        archivos = [os.path.join(DIR_CACHE_VOZ, f)
                    for f in os.listdir(DIR_CACHE_VOZ)]
    except Exception:
        return
    if len(archivos) <= _CACHE_LIMITE:
        return
    archivos.sort(key=lambda r: os.path.getmtime(r))
    for r in archivos[:len(archivos) - _CACHE_LIMITE]:
        try:
            os.remove(r)
        except Exception:
            pass


_CONTADOR_VOZ = 0
_lock_contador = threading.Lock()


def _marcar_voz_activa(activa):
    """Lleva la cuenta de reproducciones en curso (para evitar doble audio)."""
    global _CONTADOR_VOZ
    with _lock_contador:
        _CONTADOR_VOZ += 1 if activa else -1
        if _CONTADOR_VOZ < 0:
            _CONTADOR_VOZ = 0


def hay_voz_activa():
    """True si hay TTS reproduciéndose ahora mismo (o en la cola de voz)."""
    with _lock_contador:
        return _CONTADOR_VOZ > 0 or not _COLA_VOZ.empty()


def _hablar_core(texto, on_inicio=None, on_fin=None):
    """Sintetiza (con caché) y reproduce `texto`; llama a los callbacks.
    Usada por hablar() y por el hilo consumidor de fragmentos."""
    if on_inicio:
        try:
            on_inicio()
        except Exception:
            pass
    _marcar_voz_activa(True)
    try:
        ruta = _sintetizar_con_cache(texto)
        _reproducir(ruta)
    except Exception:
        pass
    finally:
        _marcar_voz_activa(False)
    if on_fin:
        try:
            on_fin()
        except Exception:
            pass


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

    threading.Thread(target=_hablar_core,
                     args=(texto, on_inicio, on_fin), daemon=True).start()


def hablar_sincrono(texto):
    """Habla bloqueante (para pruebas/CLI)."""
    if not _existe_voz(texto):
        return
    with _mutex:
        if _es_voz_edge(VOZ) and edge_tts is None:
            return
    try:
        ruta = _sintetizar_con_cache(texto)
        _reproducir(ruta)
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
                _hablar_core(texto)
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
DIR_MODELO_VOSK = os.path.join(_DIR, "data", "vosk", "vosk-model-small-es-0.3")
_vosk_modelo = None
_lock_vosk = threading.Lock()


def _vosk_disponible():
    """True si vosk está instalado y el modelo es-0.3 está en disco."""
    try:
        import vosk  # noqa: F401
    except Exception:
        return False
    return os.path.exists(os.path.join(DIR_MODELO_VOSK, "Gr.fst")) and \
        os.path.exists(os.path.join(DIR_MODELO_VOSK, "final.mdl"))


def _motor_stt_activo():
    if MOTOR_STT == "vosk":
        return "vosk" if _vosk_disponible() else "google"
    if MOTOR_STT == "google":
        return "google"
    # auto: Vosk local si se puede, Google como respaldo
    return "vosk" if _vosk_disponible() else "google"


def _obtener_vosk():
    """Carga perezosa del modelo Vosk (una vez). Necesita vosk instalado."""
    global _vosk_modelo
    if _vosk_modelo is not None:
        return _vosk_modelo
    with _lock_vosk:
        if _vosk_modelo is None:
            from vosk import Model
            _vosk_modelo = Model(DIR_MODELO_VOSK)
    return _vosk_modelo


def _transcribir_vosk(audio):
    """Transcribe `audio` (sr.AudioData) con Vosk local; sin internet."""
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(_obtener_vosk(), 16000)
    datos = audio.get_raw_data(convert_rate=16000, convert_width=2, convert_channels=1)
    if rec.AcceptWaveform(datos):
        res = json.loads(rec.Result())
    else:
        res = json.loads(rec.FinalResult())
    return (res.get("text") or "").strip()


def _grabar(duracion_max=None, silencio=None):
    """Graba con el micrófono y devuelve sr.AudioData."""
    if sr is None or pyaudio is None:
        raise RuntimeError("speech_recognition/pyaudio no disponible")
    if duracion_max is None:
        duracion_max = DURACION_MAX
    if silencio is None:
        silencio = SILENCIO
    r = sr.Recognizer()
    r.pause_threshold = silencio
    # Ajusta los umbrales de energía y silencio para frases largas naturales.
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    r.dynamic_energy_adjustment_damping = 0.15
    with sr.Microphone() as fuente:
        r.adjust_for_ambient_noise(fuente, duration=0.6)
        try:
            audio = r.listen(fuente, timeout=duracion_max, phrase_time_limit=duracion_max)
        except sr.WaitTimeoutError:
            raise TimeoutError("No se detectó voz a tiempo")
    return r, audio


def escuchar(duracion_max=None, silencio=None):
    """Escucha y devuelve (texto, error). texto="" si no entendió, error con descripción.
    Usa Vosk local si está disponible/configurado; Google es-MX como respaldo."""
    _recargar_config()
    try:
        r, audio = _grabar(duracion_max, silencio)
    except TimeoutError:
        return "", "silencioso"
    except Exception as e:
        return "", f"micrófono: {e}"
    motor = _motor_stt_activo()
    if motor == "vosk":
        try:
            texto = _transcribir_vosk(audio)
            return texto, None
        except Exception as e:
            if MOTOR_STT in ("auto",):
                pass  # fallback a Google
            else:
                return "", f"vosk: {e}"
    if sr is None:
        return "", "speech_recognition no disponible"
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