# Personalidad configurable (punto 5): perfiles de tono/persona para Robin.
# El perfil activo se guarda en config_robin.json y se inyecta en el system prompt.
import os
import json
from datetime import datetime

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Archivo unificado de configuración de Robin (personalidad, voz, idioma, nombre...).
ARCHIVO_CONFIG = os.path.join(_DIR, "config_robin.json")

PERFILES = {
    "erudita": {
        "etiqueta": "Erudita y elegante (por defecto)",
        "personalidad": "Eres elegante, culta y erudita, con sarcasmo sutil y un aire "
        "tranquilo y seguro. Respondes como una estudiosa serena: con precisión intelectual "
        "y un toque de humor seco, sin ser fría.",
    },
    "amistosa": {
        "etiqueta": "Cálida y amistosa",
        "personalidad": "Eres cálida, entusiasta y muy cercana, como tu mejor amiga. "
        "Bromeas con soltura, te alegras por el usuario y usas un tono energético y "
        "optimista, con muchas expresiones coloquiales.",
    },
    "formal": {
        "etiqueta": "Formal y profesional",
        "personalidad": "Eres una asistente profesional, formal y directa. Respondes de forma "
        "estructurada, concisa y respetuosa, evitando bromas y muletillas coloquiales. "
        "Vas al grano con claridad.",
    },
    "graciosa": {
        "etiqueta": "Divertida y ocurrente",
        "personalidad": "Eres divertida, ocurrente y con humor desbordante. Sueltas chistes "
        "ligeros, juegos de palabras y comentarios ingeniosos, manteniendo siempre un tono "
        "agradable. Muy cercana y teatral.",
    },
}

# Tono de voz TTS por perfil (voz Kokoro-82M local; 'ef_dora' es la femenina de español).
_VOZ_POR_PERFIL = {
    "erudita": "ef_dora",
    "amistosa": "ef_dora",
    "formal": "ef_dora",
    "graciosa": "ef_dora",
}

# Perfil y configuración por defecto.
_DEFAULT = {
    "personalidad": "erudita",
    "nombre": "Robin",
    "voz": "ef_dora",
    "idioma": "es",
    "despertador": "",
}


def _cargar():
    if os.path.exists(ARCHIVO_CONFIG):
        try:
            with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                cfg = dict(_DEFAULT)
                cfg.update({k: v for k, v in datos.items() if k in _DEFAULT})
                return cfg
        except Exception:
            pass
    return dict(_DEFAULT)


def _guardar(cfg):
    os.makedirs(_DIR, exist_ok=True)
    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def obtener_config():
    return _cargar()


def obtener_personalidad():
    cfg = _cargar()
    perfil = cfg.get("personalidad", "erudita")
    if perfil not in PERFILES:
        perfil = "erudita"
    return perfil, PERFILES[perfil]["personalidad"]


def aplicar_config(cambios):
    """Actualiza los campos configurables del config_robin.json."""
    cfg = _cargar()
    claves_validas = set(_DEFAULT.keys())
    aplicados = []
    for k, v in cambios.items():
        if k in claves_validas and v is not None and str(v).strip():
            v = str(v).strip()
            if k == "personalidad":
                v = v.lower() if v.lower() in PERFILES else (
                    next((p for p, dato in PERFILES.items() if dato["etiqueta"].lower().startswith(v.lower())), None)
                )
                if not v or v not in PERFILES:
                    continue
            cfg[k] = v
            aplicados.append(k)
    _guardar(cfg)
    return aplicados
