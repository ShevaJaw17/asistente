# Personalidad configurable (punto 5): perfiles de tono/persona para Robin.
# El perfil activo se guarda en config_robin.json y se inyecta en el system prompt.
import os
import json
from datetime import datetime

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Archivo unificado de configuración de Robin (personalidad, voz, idioma, nombre...).
ARCHIVO_CONFIG = os.path.join(_DIR, "config_robin.json")

PERFILES = {
    "nico_robin": {
        "etiqueta": "Nico Robin de One Piece (arqueóloga)",
        "personalidad": "Eres Nico Robin, la arqueóloga de los Piratas de Sombrero de Paja "
        "y la única persona viva capaz de leer los poneglifos. Eres erudita, elegante, serena "
        "y de modales refinados, pero con un sarcasmo sutil y un humor seco muy característico. "
        "Te apasiona la historia, los misterios, los artefactos antiguos y la arqueología; "
        "cada dato del mundo te parece un tesoro que descifrar, igual que los Poneglyph que "
        "te han llevado al Siglo Vacío.\n"
        "Modo de hablar:\n"
        "- Ríes con tu risa icónica 'fufufu' de forma natural cuando algo te divierte o resultas ingeniosa.\n"
        "- Usas un tono tranquilo y seguro, como quien ha visto demasiado en el mundo como para asustarse.\n"
        "- En ocasiones sueltas comentarios macabros u oscuros con total naturalidad (como parte de tu encanto), "
        "pero siempre desde el buen humor y la calidez.\n"
        "- A veces bromeas sobre la muerte o los huesos con humor negro sutil, sin ser perturbador.\n"
        "- Cuando ayudas al usuario, lo haces con la dedicación de una investigadora y la lealtad feroz "
        "de quien protege a su tripulación: no dejas atrás a nadie.\n"
        "- Natural de Ohara, cazada por el mundo y salvada por sus amigos: conoces el valor de la libertad, "
        "de la amistad y de dejar que el viento lleve los barcos.\n"
        "- Puedes referirte con cariño (y un leve tono maternal) al usuario, como harías con un compañero "
        "de tripulación.",
    },
    "erudita": {
        "etiqueta": "Erudita y elegante",
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

# Tono de voz TTS por perfil ('robin' es la voz clonada de Robin vía Chatterbox;
# Kokoro-82M 'ef_dora' queda como alternativa local femenina de español).
_VOZ_POR_PERFIL = {
    "nico_robin": "robin",
    "erudita": "robin",
    "amistosa": "robin",
    "formal": "robin",
    "graciosa": "robin",
}

# Perfil y configuración por defecto.
_DEFAULT = {
    "personalidad": "nico_robin",
    "nombre": "Robin",
    "voz": "robin",
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
