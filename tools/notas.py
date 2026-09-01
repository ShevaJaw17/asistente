# Tools de notas rápidas (diario acumulativo) en notas.json.
from datetime import datetime

import tools.asistente_util as util
import tools.registro as reg


def cargar():
    return util.cargar("notas", [])


def guardar(n):
    util.guardar("notas", n)


@reg.registrar(
    "agregar_nota",
    descripcion="Guarda una nota rápida o idea con su fecha, como un diario acumulativo.",
    parametros={"texto": {"type": "string", "description": "El contenido de la nota o idea.", "requerido": True}},
)
def agregar(texto):
    texto = (texto or "").strip()
    if not texto:
        return "Error: falta el texto de la nota."
    n = cargar()
    n.append({"texto": texto, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")})
    guardar(n)
    return f"Nota guardada (nº {len(n)}): {texto}"


@reg.registrar("listar_notas", descripcion="Muestra todas las notas guardadas, de la más reciente a la más antigua.")
def listar():
    n = cargar()
    if not n:
        return "No tienes ninguna nota guardada."
    return "\n".join(
        f"{i}. [{x.get('fecha', '?')}] {x['texto']}" for i, x in enumerate(reversed(n), 1)
    )


@reg.registrar(
    "borrar_nota",
    descripcion="Elimina una nota guardada por su número de lista.",
    parametros={"indice": {"type": "integer", "description": "Número de la nota a eliminar (según listar_notas).", "requerido": True}},
)
def borrar(indice):
    try:
        idx = int(indice)
    except (TypeError, ValueError):
        return "Error: índice inválido."
    n = cargar()
    if idx < 1 or idx > len(n):
        return f"Error: no existe la nota número {idx}."
    texto = n.pop(idx - 1)["texto"]
    guardar(n)
    return f"Nota eliminada: {texto}"
