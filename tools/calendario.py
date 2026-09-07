# Calendario local: exporta la agenda recurrente del asistente a formato iCalendar
# (.ics) que se puede importar en Google Calendar, Outlook, Apple Calendar, etc.
import os
import re
from datetime import datetime, timedelta

import tools.asistente_util as util
import tools.registro as reg

_DIAS_ICS = {
    "lunes": "MO", "martes": "TU", "miercoles": "WE",
    "jueves": "TH", "viernes": "FR", "sabado": "SA", "domingo": "SU",
    "lun": "MO", "mar": "TU", "mie": "WE", "jue": "TH", "vie": "FR", "sab": "SA", "dom": "SU",
}


def _a_ics_filename(texto):
    return re.sub(r"[\\/:*?\"<>|]", "-", (texto or "calendario")).strip()[:60]


def _siguiente_fecha(dias, hora):
    """Calcula la siguiente fecha/hora futura en la que toca la tarea."""
    ahora = datetime.now()
    _, h, m = (hora or "08:00").replace(".", ":").partition(":") or ("8", ":", "0")
    try:
        h, m = int(h or 8), int(m or 0)
    except ValueError:
        h, m = 8, 0
    if not dias or dias.strip() == "*":
        candidata = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidata <= ahora:
            candidata += timedelta(days=1)
        return candidata
    set_dias = set()
    for d in dias.split(","):
        d = _DIAS_ICS.get(d.strip().lower()[:3], "")
        if d:
            set_dias.add(d)
    candidata = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    for _ in range(8):
        if candidata.weekday() < 5 and candidata.strftime("%a").upper() in set_dias:
            break
        candidata += timedelta(days=1)
    if candidata <= ahora:
        candidata += timedelta(days=7)
    return candidata


def _fmt_dt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")


@reg.registrar(
    "exportar_agenda_ics",
    descripcion=(
        "Exporta la agenda recurrente del asistente a un archivo .ics (iCalendar) "
        "que se puede importar en Google Calendar, Outlook, Apple Calendar, etc. "
        "Guarda el archivo en la carpeta Documentos."
    ),
    parametros={
        "nombre_archivo": {"type": "string", "description": "Nombre del archivo .ics de salida."},
    },
)
def exportar_agenda_ics(nombre_archivo=None):
    try:
        import programador
    except ImportError:
        return "No se pudo acceder al módulo de agenda."
    tareas = programador.cargar()
    if not tareas:
        return "No hay tareas programadas para exportar."
    eventos = []
    for t in tareas:
        if not t.get("activa", True):
            continue
        nombre = t.get("nombre", "evento")
        dias = t.get("dias", "*")
        hora = t.get("hora", "08:00")
        dtstart = _siguiente_fecha(dias, hora)
        dt_str = _fmt_dt(dtstart)
        set_dias = set()
        for d in (dias or "").split(","):
            d = _DIAS_ICS.get(d.strip().lower()[:3], "")
            if d:
                set_dias.add(d)
        if not set_dias or dias.strip() == "*":
            rrule = "FREQ=DAILY;INTERVAL=1"
        else:
            rrule = f"FREQ=WEEKLY;BYDAY={','.join(sorted(set_dias))}"
        accion = t.get("accion", "aviso")
        desc = t.get("parametros", {})
        if isinstance(desc, dict):
            desc = desc.get("texto", accion)
        desc = (desc or accion).replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;")
        eventos.append(
            "BEGIN:VEVENT\n"
            f"DTSTART;TZID=America/Mexico_City:{dt_str}\n"
            f"RRULE:{rrule}\n"
            f"SUMMARY:{nombre}\n"
            f"DESCRIPTION:{desc}\n"
            f"UID:{t.get('id', hash(nombre))}@asistente-local\n"
            "END:VEVENT"
        )
    carpeta = os.path.join(os.path.expanduser("~"), "Documents")
    try:
        import ctypes.wintypes
        from ctypes import windll
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
        if buf.value:
            carpeta = buf.value
    except Exception:
        pass
    try:
        os.makedirs(carpeta, exist_ok=True)
    except Exception:
        pass
    base = _a_ics_filename(nombre_archivo or "agenda_asistente")
    ruta = os.path.join(carpeta, f"{base}.ics")
    cal = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//AsistenteVirtual//NicoRobin//ES\n"
        "CALSCALE:GREGORIAN\n"
        "METHOD:PUBLISH\n"
        "X-WR-TIMEZONE:America/Mexico_City\n"
        + "\n".join(eventos) + "\n"
        "END:VCALENDAR\n"
    )
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(cal)
    except Exception as e:
        return f"Error al guardar el .ics: {e}"
    return f"Agenda exportada a:\n{ruta}\nImporta el archivo en tu calendario favorito."
