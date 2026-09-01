# Agenda recurrente: recordatorios que se repiten por día/semana.
# Capa de alto nivel sobre el programador: convierte nombres de días en español
# (o 'diario'/'semanal') a la configuración de días que entiende programador.py.
import programador
import tools.registro as reg

# Mapeo de nombres de días en español a números (0=Lunes ... 6=Domingo).
_DIAS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    "semana": "*", "lunes a viernes": [0, 1, 2, 3, 4], "laborables": [0, 1, 2, 3, 4],
    "fin de semana": [5, 6], "finde": [5, 6],
}


def _parsear_dias(texto):
    """Convierte 'todos', 'diario', 'lunes y jueves', etc. a especificación de días."""
    t = (texto or "").strip().lower()
    if not t or t in ("*", "todos", "todo", "diario", "diaria", "cada dia", "cada día"):
        return "*"
    # Separar por comas, 'y' y 'e'.
    partes = [p.strip() for p in t.replace(" y ", ",").replace(" e ", ",").split(",")]
    dias = []
    for p in partes:
        if not p:
            continue
        clave = p
        if clave in _DIAS and _DIAS[clave] == "*":
            return "*"
        if clave in _DIAS and isinstance(_DIAS[clave], list):
            dias.extend(_DIAS[clave])
        elif clave in _DIAS and isinstance(_DIAS[clave], int):
            dias.append(_DIAS[clave])
        else:
            # ¿año con hora "lunes" suelto con variantes?
            return None  # no reconocido
    # deduplicar y ordenar
    unicos = sorted(set(d for d in dias if isinstance(d, int)))
    return unicos if unicos else "*"


def _descripcion_dias(dias):
    if dias == "*":
        return "todos los días"
    nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    return ", ".join(nombres[d] for d in dias)


@reg.registrar(
    "agregar_agenda_recurrente",
    descripcion=(
        "Programa un recordatorio o acción que se repite en días concretos de la semana o "
        "todos los días. Acepta días en español: 'todos los días', 'diario', 'los lunes', "
        "'lunes y jueves', 'lunes a viernes', 'fin de semana'. Ej: 'programa que todos los "
        "días a las 8:00 me avises de desayunar', 'los lunes y miércoles a las 18:00 limpiar "
        "temporales'. Es una agenda recurrente."
    ),
    parametros={
        "nombre": {"type": "string", "description": "Nombre o descripción de la tarea (ej. 'Desayunar').", "requerido": True},
        "hora": {"type": "string", "description": "Hora en formato HH:MM, ej. '08:00'.", "requerido": True},
        "dias": {"type": "string", "description": "Días en español: 'todos', 'diario', 'lunes', 'lunes y jueves', 'lunes a viernes', 'fin de semana'. Opcional, por defecto todos los días.", "requerido": True},
        "accion": {"type": "string", "description": "Tipo de acción: 'aviso' (por defecto), 'comando', 'abrir', 'sistema:...'."},
        "parametros": {"type": "object", "description": "Parámetros según acción (ver programador). Para 'aviso': {'texto': '...'}."},
    },
)
def agregar(nombre, hora, dias, accion="aviso", parametros=None):
    dias_ok = _parsear_dias(dias)
    if dias_ok is None:
        return "Error: no entendí los días. Usa 'todos', 'diario', 'lunes', 'lunes y jueves', 'lunes a viernes' o 'fin de semana'."
    r = programador.agregar(nombre, hora, dias=dias_ok, accion=accion, parametros=parametros)
    return r


@reg.registrar(
    "listar_agenda",
    descripcion="Muestra la agenda recurrente (tareas programadas) con hora, días y estado.",
)
def listar():
    return programador.listar()


@reg.registrar(
    "borrar_agenda",
    descripcion="Elimina un elemento de la agenda recurrente por su número (según listar_agenda).",
    parametros={"indice": {"type": "integer", "description": "Número del elemento de agenda a eliminar.", "requerido": True}},
)
def borrar(indice):
    return programador.borrar(indice)
