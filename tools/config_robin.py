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
        return True
    except Exception:
        return False


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
    descripcion="Cambia la personalidad de Robin. Perfiles: 'erudita', 'amistosa', 'formal' o 'graciosa'.",
    parametros={"perfil": {"type": "string", "description": "Nombre del perfil: erudita, amistosa, formal o graciosa.", "requerido": True}},
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
    descripcion="Cambia la voz de TTS. Ejemplos: es-MX-DaliaNeural, es-ES-AlvaroNeural, es-US-JennyNeural. Usa listar_voces para ver opciones.",
    parametros={"voz": {"type": "string", "description": "Identificador de voz edge-tts.", "requerido": True}},
)
def cambiar_voz(voz):
    voz = (voz or "").strip()
    if not voz or ".Neural" not in voz:
        return "Formato de voz no válido. Ejemplos: es-MX-DaliaNeural, es-ES-AlvaroNeural."
    aplicados = personalidad.aplicar_config({"voz": voz})
    ok = _actualizar_voz_txt(voz)
    if "voz" in aplicados and ok:
        return f"Voz cambiada a {voz}."
    return "No pude cambiar la voz."


@reg.registrar(
    "listar_voces",
    descripcion="Muestra voces de TTS recomendadas (español) para Robin.",
)
def listar_voces():
    return (
        "Voces TTS disponibles (español):\n"
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
    return (
        f"Configuración de Robin:\n"
        f"- Nombre: {cfg.get('nombre')}\n"
        f"- Personalidad: {perfil} ({personalidad.PERFILES.get(perfil, {}).get('etiqueta')})\n"
        f"- Voz TTS: {cfg.get('voz')}"
    )
