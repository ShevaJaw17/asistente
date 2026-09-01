# Memoria explícita clave-valor (memoria.json) + memoria semántica a largo plazo.
import os

import tools.asistente_util as util
import tools.registro as reg


def cargar_memoria():
    return util.cargar("memoria", {})


def guardar_memoria(m):
    util.guardar("memoria", m)


@reg.registrar(
    "recordar",
    descripcion=(
        "Guarda en memoria una preferencia o dato que el usuario pide recordar "
        "para el futuro. Ej: 'recuerda que me llamo Juan', 'recuerda que odio el café'. "
        "Devuelve lo guardado."
    ),
    parametros={
        "clave": {"type": "string", "description": "Etiqueta corta (ej. 'nombre', 'gusto').", "requerido": True},
        "valor": {"type": "string", "description": "El dato o preferencia a recordar.", "requerido": True},
    },
)
def recordar(clave, valor):
    clave = (clave or "").strip().lower()
    valor = (valor or "").strip()
    if not clave or not valor:
        return "Error: faltan clave o valor."
    m = cargar_memoria()
    m[clave] = valor
    guardar_memoria(m)
    return f"Recordado: {clave} = {valor}"


@reg.registrar(
    "que_recuerdas",
    descripcion="Devuelve todas las preferencias y datos que el asistente tiene guardados en memoria.",
)
def que_recuerdas():
    m = cargar_memoria()
    if not m:
        return "No tengo nada guardado en memoria."
    return "\n".join(f"- {k}: {v}" for k, v in m.items())


@reg.registrar(
    "olvidar",
    descripcion="Elimina de la memoria un dato guardado previamente.",
    parametros={"clave": {"type": "string", "description": "La clave del dato que se desea olvidar.", "requerido": True}},
)
def olvidar(clave):
    clave = (clave or "").strip().lower()
    m = cargar_memoria()
    if clave in m:
        del m[clave]
        guardar_memoria(m)
        return f"Olvidado: {clave}"
    return f"No hay nada guardado con la clave '{clave}'."
