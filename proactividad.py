# proactividad.py - Reglas para que el asistente tome iniciativa por su cuenta:
# saludo diario y avisos según la franja horaria. Cada regla se dispara como
# máximo una vez al día.
import json
import os
from datetime import datetime

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proactividad.json")


def _cargar():
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                return datos
        except Exception:
            pass
    return {}


def _guardar(datos):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def clave_saludo():
    return "ultimo_saludo"


def saludo_pendiente(ahora=None):
    """Devuelve hoy (la fecha a marcar) si el usuario aún no fue saludado hoy.
    Solo en franja matinal (7:00-15:00); el resto del día lo cubren los avisos."""
    ahora = ahora or datetime.now()
    if ahora.hour < 7 or ahora.hour >= 15:
        return None
    hoy = ahora.strftime("%Y-%m-%d")
    datos = _cargar()
    if datos.get(clave_saludo()) == hoy:
        return None
    return hoy


def aviso_pendiente(ahora=None):
    """Devuelve (clave, hoy) de la primera regla de aviso que toca y no se ha
    disparado hoy. Reglas en minutos desde medianoche."""
    ahora = ahora or datetime.now()
    hoy = ahora.strftime("%Y-%m-%d")
    minuto = ahora.hour * 60 + ahora.minute
    datos = _cargar()
    reglas = [
        ("tarde", 17 * 60 + 45, 22 * 60, "laboral"),
        ("noche", 23 * 60, 24 * 60, "cualquier"),
    ]
    for clave, inicio, fin, tipo in reglas:
        if minuto < inicio or minuto >= fin:
            continue
        if tipo == "laboral" and ahora.weekday() >= 5:
            continue
        if datos.get(clave) == hoy:
            continue
        return (clave, hoy)
    return None


def marcar(clave):
    datos = _cargar()
    datos[clave] = datetime.now().strftime("%Y-%m-%d")
    _guardar(datos)


def pendiente_ahora(ahora=None):
    """Devuelve (clave, hoy) con la acción proactiva más urgente (saludo primero)."""
    ahora = ahora or datetime.now()
    saludo = saludo_pendiente(ahora)
    if saludo:
        return (clave_saludo(), saludo)
    return aviso_pendiente(ahora)