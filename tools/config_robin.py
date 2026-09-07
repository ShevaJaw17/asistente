# Configuración de Robin editable desde el chat (punto 5 personalidad + punto 3 configuración).
# Persiste en data/config_robin.json y escribe también en voz_config.json cuando se cambia la voz.
import os
import json

import personalidad
import tools.registro as reg

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_ARCHIVO_VOZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voz_config.json")


def _actualizar_voz_txt(voz):
    """Escribe la voz elegida en voz_config.json (lo usa TTS)."""
    try:
        ruta = _ARCHIVO_VOZ
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        else:
            cfg = {}
        cfg["voz"] = voz
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        try:
            import voz as _voz
            _voz.aplicar_config({})
        except Exception:
            pass
        return True
    except Exception:
        return False


@reg.registrar(
    "configurar_dictado",
    descripcion="Configura el dictado por voz: duración máxima de la frase (duracion_max en segundos), pausa que cierra la frase (silencio en segundos) y motor de reconocimiento (auto, vosk local sin internet, o google). Ej: 'configura el dictado con motor vosk y silencio de 2 segundos'.",
    parametros={
        "duracion_max": {"type": "number", "description": "Segundos máximos de una frase (1-30)."},
        "silencio": {"type": "number", "description": "Segundos de pausa que cierran la frase (0.5-5)."},
        "motor_stt": {"type": "string", "description": "Motor STT: 'auto', 'vosk' (local) o 'google'."},
    },
)
def configurar_dictado(duracion_max=None, silencio=None, motor_stt=None):
    try:
        import voz as _voz
    except Exception:
        return "No puedo aplicar el dictado (módulo de voz no disponible)."
    cambios = {}
    if duracion_max is not None:
        cambios["duracion_max"] = max(1.0, min(30.0, float(duracion_max)))
    if silencio is not None:
        cambios["silencio"] = max(0.5, min(5.0, float(silencio)))
    if motor_stt:
        motor_stt = str(motor_stt).strip().lower()
        if motor_stt not in ("auto", "vosk", "google"):
            return "Motor STT no válido: usa auto, vosk o google."
        cambios["motor_stt"] = motor_stt
    if not cambios:
        return "Dime qué quieres ajustar: duración (duracion_max), silencio o motor (auto/vosk/google)."
    try:
        ok = _voz.aplicar_config(cambios)
    except Exception:
        ok = False
    if not ok:
        return "No pude aplicar el dictado."
    vcfg = {}
    try:
        with open(_ARCHIVO_VOZ, "r", encoding="utf-8") as f:
            vcfg = json.load(f)
    except Exception:
        pass
    return (
        "Dictado configurado:\n"
        f"- Duración máx: {vcfg.get('duracion_max', 20.0)}s\n"
        f"- Silencio: {vcfg.get('silencio', 1.8)}s\n"
        f"- Motor STT: {vcfg.get('motor_stt', 'auto')}"
    )


@reg.registrar(
    "listar_perfiles",
    descripcion="Muestra los perfiles de personalidad disponibles para Robin y cuál está activo.",
)
def listar_perfiles():
    perfil_actual, _ = personalidad.obtener_personalidad()
    lineas = ["Perfiles de personalidad de Robin:"]
    for key, dato in personalidad.PERFILES.items():
        marco = " [ACTIVO]" if key == perfil_actual else ""
        lineas.append(f"- {key}: {dato['etiqueta']}{marco}")
    return "\n".join(lineas)


@reg.registrar(
    "cambiar_personalidad",
    descripcion="Cambia la personalidad de Robin. Perfiles: 'nico_robin' (One Piece), 'erudita', 'amistosa', 'formal' o 'graciosa'.",
    parametros={"perfil": {"type": "string", "description": "Nombre del perfil: nico_robin, erudita, amistosa, formal o graciosa.", "requerido": True}},
)
def cambiar_personalidad(perfil):
    perfil_norm = (perfil or "").strip().lower()
    if perfil_norm not in personalidad.PERFILES:
        return "Perfil no válido. Opciones: " + ", ".join(personalidad.PERFILES.keys())
    aplicados = personalidad.aplicar_config({"personalidad": perfil_norm})
    if "personalidad" not in aplicados:
        return "No pude cambiar la personalidad."
    # Cambiar también la voz sugerida por el perfil.
    voz = personalidad._VOZ_POR_PERFIL.get(perfil_norm)
    if voz:
        personalidad.aplicar_config({"voz": voz})
        _actualizar_voz_txt(voz)
    return f"Personalidad cambiada a '{perfil_norm}': {personalidad.PERFILES[perfil_norm]['etiqueta']}. Voy a responder con ese estilo a partir de ahora."


@reg.registrar(
    "cambiar_nombre",
    descripcion="Cambia el nombre con el que te llamas (por defecto 'Robin').",
    parametros={"nombre": {"type": "string", "description": "Nuevo nombre del asistente.", "requerido": True}},
)
def cambiar_nombre(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        return "Error: dime un nombre."
    aplicados = personalidad.aplicar_config({"nombre": nombre})
    if "nombre" not in aplicados:
        return "No pude cambiar el nombre."
    return f"Listo, a partir de ahora me llamo {nombre}."


@reg.registrar(
    "cambiar_voz",
    descripcion="Cambia la voz de TTS. Robin (clonada local): 'robin'. Kokoro (local): 'ef_dora' (femenino), 'em_alex', 'em_santa' (masculino). edge-tts: es-MX-DaliaNeural, etc. Usa listar_voces para ver opciones.",
    parametros={"voz": {"type": "string", "description": "Identificador de voz (robin, Kokoro o edge-tts).", "requerido": True}},
)
def cambiar_voz(voz):
    voz = (voz or "").strip()
    valida = (
        voz.lower() == "robin"
        or ".Neural" in voz
        or voz[:3].lower() in ("ef_", "em_")
    )
    if not voz or not valida:
        return "Formato de voz no válido. Ejemplos (Robin): robin. (Kokoro): ef_dora, em_alex. (edge-tts): es-MX-DaliaNeural."
    aplicados = personalidad.aplicar_config({"voz": voz})
    ok = _actualizar_voz_txt(voz)
    if "voz" in aplicados and ok:
        return f"Voz cambiada a {voz}."
    return "No pude cambiar la voz."


@reg.registrar(
    "listar_voces",
    descripcion="Muestra voces de TTS disponibles (español) para Robin.",
)
def listar_voces():
    return (
        "Voces TTS disponibles (español):\n"
        "Robin (clonada local, Chatterbox):\n"
        "- robin (la voz doblada de Nico Robin)\n"
        "Kokoro (local, más natural):\n"
        "- ef_dora (femenino)\n"
        "- em_alex (masculino)\n"
        "- em_santa (masculino)\n"
        "edge-tts (fallback):\n"
        "- es-MX-DaliaNeural (femenino, MX)\n"
        "- es-MX-JorgeNeural (masculino, MX)\n"
        "- es-ES-AlvaroNeural (masculino, ES)\n"
        "- es-ES-ElviraNeural (femenino, ES)\n"
        "- es-US-JennyNeural (femenino, US)\n"
        "Para cambiarla: cambia_mi_voz a <codigo>"
    )


@reg.registrar(
    "ver_config",
    descripcion="Muestra la configuración actual de Robin: personalidad, nombre y voz.",
)
def ver_config():
    cfg = personalidad.obtener_config()
    perfil, _ = personalidad.obtener_personalidad()
    vcfg = personalidad.obtener_config()
    try:
        with open(_ARCHIVO_VOZ, "r", encoding="utf-8") as f:
            import json as _json
            vcfg = _json.load(f)
    except Exception:
        pass
    return (
        f"Configuración de Robin:\n"
        f"- Nombre: {cfg.get('nombre')}\n"
        f"- Personalidad: {perfil} ({personalidad.PERFILES.get(perfil, {}).get('etiqueta')})\n"
        f"- Voz TTS: {vcfg.get('voz')} (idioma dictado: {vcfg.get('idioma_stt')})\n"
        f"- Motor de reconocimiento: {vcfg.get('motor_stt', 'auto')}\n"
        f"- Dictado: duración máx {vcfg.get('duracion_max', 20.0)}s, silencio {vcfg.get('silencio', 1.8)}s"
    )
