# Tools de tareas (todo list) con persistencia en tareas.json.
import tools.asistente_util as util
import tools.registro as reg


def cargar():
    return util.cargar("tareas", [])


def guardar(t):
    util.guardar("tareas", t)


@reg.registrar(
    "agregar_tarea",
    descripcion="Añade una nueva tarea a la lista de pendientes.",
    parametros={"tarea": {"type": "string", "description": "La descripción de la tarea.", "requerido": True}},
)
def agregar(tarea):
    tarea = (tarea or "").strip()
    if not tarea:
        return "Error: falta la descripción de la tarea."
    t = cargar()
    t.append({"texto": tarea, "completada": False})
    guardar(t)
    return f"Tarea añadida en la posición {len(t)}: {tarea}"


@reg.registrar("listar_tareas", descripcion="Muestra la lista de tareas pendientes y completadas.")
def listar():
    t = cargar()
    if not t:
        return "La lista de tareas está vacía."
    return "\n".join(
        f"{i}. {('[x]' if x.get('completada') else '[ ]')} {x['texto']}"
        for i, x in enumerate(t, 1)
    )


@reg.registrar(
    "completar_tarea",
    descripcion="Marca una tarea de la lista como completada.",
    parametros={"indice": {"type": "integer", "description": "Número de la tarea a completar.", "requerido": True}},
)
def completar(indice):
    return _marcar_borrar("completar", indice)


@reg.registrar(
    "borrar_tarea",
    descripcion="Elimina una tarea de la lista de pendientes.",
    parametros={"indice": {"type": "integer", "description": "Número de la tarea a eliminar.", "requerido": True}},
)
def borrar(indice):
    return _marcar_borrar("borrar", indice)


def _marcar_borrar(accion, indice):
    try:
        idx = int(indice)
    except (TypeError, ValueError):
        return "Error: índice inválido."
    t = cargar()
    if idx < 1 or idx > len(t):
        return f"Error: no existe la tarea número {idx}."
    if accion == "completar":
        t[idx - 1]["completada"] = True
        guardar(t)
        return f"Tarea {idx} completada: {t[idx - 1]['texto']}"
    texto = t.pop(idx - 1)["texto"]
    guardar(t)
    return f"Tarea eliminada: {texto}"
