# Helpers compartidos para las tools: rutas a los datos y log liviano.
import json
import os

DIRECTORIO_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_RUTAS = {
    "memoria": lambda: os.path.join(DIRECTORIO_PROYECTO, "memoria.json"),
    "tareas": lambda: os.path.join(DIRECTORIO_PROYECTO, "tareas.json"),
    "notas": lambda: os.path.join(DIRECTORIO_PROYECTO, "notas.json"),
    "historial": lambda: os.path.join(DIRECTORIO_PROYECTO, "historial.json"),
}


def ruta(nombre):
    return _RUTAS[nombre]()


def cargar(nombre, defecto):
    r = ruta(nombre)
    if os.path.exists(r):
        try:
            with open(r, "r", encoding="utf-8") as f:
                dato = json.load(f)
                if isinstance(dato, type(defecto)) or defecto is None:
                    return dato
                return defecto
        except Exception:
            return defecto
    return defecto


def guardar(nombre, dato):
    with open(ruta(nombre), "w", encoding="utf-8") as f:
        json.dump(dato, f, ensure_ascii=False, indent=2)


def log(mensaje):
    try:
        print(f"[tools] {mensaje}")
    except Exception:
        pass


# Hook de confirmación: la GUI (interfaz.py) o la CLI lo sobrescriben para
# pedir confirmación al usuario antes de acciones sensibles. Por defecto
# cancela la acción (seguro por omisión).
_confirmar_hook = None


def set_confirmar_hook(fn):
    global _confirmar_hook
    _confirmar_hook = fn


def pedir_confirmacion(mensaje):
    if _confirmar_hook is not None:
        return bool(_confirmar_hook(mensaje))
    return False
