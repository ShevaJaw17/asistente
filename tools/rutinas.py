# Motor de rutinas y pipelines (automatizaciones reutilizables).
# Una rutina es una secuencia de pasos; cada paso ejecuta una tool con sus
# argumentos. Sirve para 'rutina de inicio del día', flujos de trabajo, etc.
import os
import json
import threading
from datetime import datetime

import tools.registro as reg

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARCHIVO = os.path.join(_DIR, "rutinas.json")

_LOCK = threading.Lock()


def _cargar():
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
        except Exception:
            pass
    return []


def _guardar(lista):
    os.makedirs(_DIR, exist_ok=True)
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


@reg.registrar(
    "crear_rutina",
    descripcion="Crea una rutina o pipeline: una secuencia de pasos donde cada paso ejecuta una tool. "
    "Cada paso es {'tool':'nombre_tool','args':{...}}. Ej: [{'tool':'abrir_app','args':{'nombre':'navegador'}},"
    "{'tool':'clima','args':{'ciudad':'Madrid'}}].",
    parametros={
        "nombre": {"type": "string", "description": "Nombre de la rutina (ej. 'inicio del dia').", "requerido": True},
        "pasos": {"type": "array", "description": "Lista de pasos, cada uno {'tool':..., 'args':{...}}.", "requerido": True},
    },
)
def crear(nombre, pasos):
    nombre = (nombre or "").strip() or f"Rutina {datetime.now():%H:%M}"
    if not isinstance(pasos, list) or not pasos:
        return "Error: la rutina necesita una lista de pasos (al menos uno)."
    for i, p in enumerate(pasos, 1):
        if not isinstance(p, dict) or not p.get("tool"):
            return f"Error: el paso {i} debe ser {{'tool':..., 'args':{...}}}."
    with _LOCK:
        lista = _cargar()
        if any(r.get("nombre", "").lower() == nombre.lower() for r in lista):
            return f"Error: ya existe una rutina llamada '{nombre}'."
        lista.append(
            {
                "id": _proximo_id(lista),
                "nombre": nombre,
                "pasos": pasos,
                "creada": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        _guardar(lista)
    return f"Rutina '{nombre}' creada con {len(pasos)} pasos."


def _proximo_id(lista):
    ids = [int(r.get("id", 0)) for r in lista if str(r.get("id", "0")).isdigit()]
    return (max(ids) + 1) if ids else 1


@reg.registrar(
    "listar_rutinas",
    descripcion="Muestra todas las rutinas/pipelines guardadas con sus pasos.",
)
def listar():
    with _LOCK:
        lista = _cargar()
    if not lista:
        return "No hay rutinas creadas."
    lineas = []
    for r in lista:
        pasos = ", ".join(f"{p.get('tool')}" for p in r.get("pasos", []))
        lineas.append(f"#{r['id']} '{r.get('nombre')}': {pasos}")
    return "\n".join(lineas)


@reg.registrar(
    "ejecutar_rutina",
    descripcion="Ejecuta una rutina/pipeline por su número (de listar_rutinas) y devuelve el resultado de cada paso.",
    parametros={"indice": {"type": "integer", "description": "Número/índice de la rutina a ejecutar.", "requerido": True}},
)
def ejecutar(indice):
    with _LOCK:
        lista = _cargar()
    idx = int(indice)
    rutina = next((r for r in lista if r.get("id") == idx), None)
    if rutina is None:
        return f"Error: no existe la rutina #{idx}."
    import tools
    resultados = []
    for pos, paso in enumerate(rutina.get("pasos", []), 1):
        tool = paso.get("tool")
        args = paso.get("args") or {}
        try:
            r = tools.ejecutar(tool, args)
        except Exception as e:
            resultados.append(f"Paso {pos} ({tool}): ERROR {e}")
            break
        resultados.append(f"Paso {pos} ({tool}): {r}")
    resumen = "\n".join(resultados)
    _log_ejecucion(rutina, resumen)
    return f"Rutina '{(rutina.get('nombre'))}' ejecutada:\n{resumen}"


def _log_ejecucion(rutina, resumen):
    try:
        ruta_log = os.path.join(_DIR, "ejecuciones.log")
        os.makedirs(_DIR, exist_ok=True)
        with open(ruta_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {rutina.get('nombre')}:\n{resumen}\n---\n")
    except Exception:
        pass


@reg.registrar(
    "borrar_rutina",
    descripcion="Elimina una rutina/pipeline por su número (de listar_rutinas).",
    parametros={"indice": {"type": "integer", "description": "Número de la rutina a borrar.", "requerido": True}},
)
def borrar(indice):
    idx = int(indice)
    with _LOCK:
        lista = _cargar()
        for i, r in enumerate(lista):
            if r.get("id") == idx:
                nombre = r.get("nombre", "?")
                lista.pop(i)
                _guardar(lista)
                return f"Rutina #{idx} eliminada: {nombre}"
    return f"Error: no existe la rutina #{idx}."
