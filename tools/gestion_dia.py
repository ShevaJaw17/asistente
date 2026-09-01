# Asistente de gestión del día (rol 'empleado'): resúmenes diarios/semanales
# que combinan clima, agenda, tareas pendientes y recordatorios, más seguimiento
# de encargos (tareas delegadas con estado).
import os
import json
from datetime import datetime, timedelta

import tools.registro as reg

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARCHIVO_ENCARGOS = os.path.join(_DIR, "encargos.json")

_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _fecha_hoy():
    return datetime.now().strftime("%Y-%m-%d")


def _obtener_clima(ciudad="Madrid"):
    try:
        import tools
        return tools.ejecutar("clima", {"ciudad": ciudad})
    except Exception as e:
        return f"(clima no disponible: {e})"


def _obtener_agenda():
    try:
        import programador
        return programador.listar()
    except Exception:
        return ""


def _obtener_tareas():
    try:
        import tools
        return tools.ejecutar("listar_tareas", {})
    except Exception:
        return ""


def _obtener_recordatorios():
    try:
        import tools
        return tools.ejecutar("listar_recordatorios", {})
    except Exception:
        return ""


@reg.registrar(
    "resumen_diario",
    descripcion="Prepara el resumen del día: fecha, clima, agenda/tareas programadas, tareas pendientes y recordatorios activos. Ideal para '¿cómo va mi día?'.",
    parametros={"ciudad": {"type": "string", "description": "Ciudad para el clima (opcional, por defecto Madrid)."}},
)
def resumen_diario(ciudad="Madrid"):
    hoy = datetime.now()
    partes = [f"Resumen del día: {hoy.strftime('%A %d/%m/%Y')}"]
    partes.append(f"**Clima**: {_obtener_clima(ciudad)}")
    agenda = _obtener_agenda()
    partes.append(f"**Agenda programada**: {agenda if agenda else 'nada programado'}")
    tareas = _obtener_tareas()
    partes.append(f"**Tareas pendientes**: {tareas if tareas else 'no hay tareas'}")
    rec = _obtener_recordatorios()
    partes.append(f"**Recordatorios**: {rec if rec else 'ninguno activo'}")
    return "\n".join(partes)


@reg.registrar(
    "resumen_semanal",
    descripcion="Prepara el resumen de la semana actual: rango de fechas y las tareas/agenda de la semana. Útil para la planificación del lunes.",
)
def resumen_semanal():
    hoy = datetime.now()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    partes = [
        f"Resumen semanal: del {lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')}",
        f"**Agenda de la semana**: {_obtener_agenda() or 'nada programado'}",
        f"**Tareas pendientes**: {_obtener_tareas() or 'no hay tareas'}",
    ]
    return "\n".join(partes)


# -------- seguimiento de encargos --------

def _cargar_encargos():
    if os.path.exists(ARCHIVO_ENCARGOS):
        try:
            with open(ARCHIVO_ENCARGOS, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
        except Exception:
            pass
    return []


def _guardar_encargos(lista):
    os.makedirs(_DIR, exist_ok=True)
    with open(ARCHIVO_ENCARGOS, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


@reg.registrar(
    "registrar_encargo",
    descripcion="Registra una tarea delegada (un encargo) con fecha límite y estado, para hacer seguimiento.",
    parametros={
        "descripcion": {"type": "string", "description": "Qué hay que hacer (encargo).", "requerido": True},
        "fecha_limite": {"type": "string", "description": "Fecha límite en formato AAAA-MM-DD (opcional)."},
        "estado": {"type": "string", "description": "Estado inicial: 'pendiente', 'en curso' o 'hecho' (opcional)."},
    },
)
def registrar_encargo(descripcion, fecha_limite=None, estado="pendiente"):
    descripcion = (descripcion or "").strip()
    if not descripcion:
        return "Error: dime qué encargo registrar."
    lista = _cargar_encargos()
    lista.append(
        {
            "id": len(lista) + 1,
            "descripcion": descripcion,
            "fecha_limite": fecha_limite or _fecha_hoy(),
            "estado": (estado or "pendiente"),
            "creada": _fecha_hoy(),
        }
    )
    _guardar_encargos(lista)
    return f"Encargo #{len(lista)} registrado: {descripcion}."


@reg.registrar(
    "listar_encargos",
    descripcion="Muestra los encargos registrados con su estado y fecha límite.",
)
def listar_encargos():
    lista = _cargar_encargos()
    if not lista:
        return "No hay encargos registrados."
    hoy = datetime.now().date()
    lineas = ["Encargos:"]
    for e in lista:
        estado = e.get("estado", "pendiente")
        limite = e.get("fecha_limite", "")
        vencida = ""
        if estado != "hecho" and limite:
            try:
                if datetime.strptime(limite, "%Y-%m-%d").date() < hoy:
                    vencida = " (VENCIDA)"
            except Exception:
                pass
        lineas.append(f"#{e['id']} [{estado}] {e.get('descripcion')} — límite {limite}{vencida}")
    return "\n".join(lineas)


@reg.registrar(
    "actualizar_encargo",
    descripcion="Cambia el estado de un encargo por su número (de listar_encargos). Estados: 'pendiente', 'en curso', 'hecho'.",
    parametros={
        "indice": {"type": "integer", "description": "Número del encargo.", "requerido": True},
        "estado": {"type": "string", "description": "Nuevo estado: pendiente, en curso o hecho.", "requerido": True},
    },
)
def actualizar_encargo(indice, estado):
    idx = int(indice)
    estado = (estado or "").strip().lower()
    if estado not in ("pendiente", "en curso", "hecho"):
        return "Estado inválido. Usa 'pendiente', 'en curso' o 'hecho'."
    lista = _cargar_encargos()
    for e in lista:
        if e.get("id") == idx:
            e["estado"] = estado
            _guardar_encargos(lista)
            return f"Encargo #{idx} actualizado a '{estado}'."
    return f"Error: no existe el encargo #{idx}."
