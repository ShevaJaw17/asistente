# Recordatorios con horario: almacenamiento en JSON + disparo de vencidos
import json
import os
import re
from datetime import datetime, timedelta

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordatorios.json")


def _formatear(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def cargar():
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
        except Exception:
            pass
    return []


def guardar(lista):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def _numeros_a_digitos(texto):
    """Convierte números en palabras presentes al inicio de la frase ('una hora',
    'media hora', 'dos minutos') a cifras decimales."""
    palabras = {
        "media": 0.5, "un": 1, "uno": 1, "una": 1, "unos": 2, "unas": 2,
        "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
        "ocho": 8, "nueve": 9, "diez": 10, "quince": 15, "veinte": 20,
        "veinticinco": 25, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
        "sesenta": 60, "noventa": 90, "cien": 100,
    }
    for palabra, valor in palabras.items():
        if texto.startswith(palabra + " "):
            return str(valor) + texto[len(palabra):]
    return texto


def parsear_hora(hora, ahora=None):
    """Acepta frase con fecha ISO 'YYYY-MM-DD HH:MM', hora 'HH:MM' (hoy o mañana),
    relativo 'en N minutos/horas/segundos' ('en media hora', 'en una hora') y
    tokens sueltos ('now', 'ahora', 'ya'). Devuelve datetime o None."""
    ahora = ahora or datetime.now()
    texto = (hora or "").strip().lower()
    if not texto:
        return None
    if re.match(r"^(now|ahora|ahorita|ya|ya mismo|enseguida|ya mismo)\b", texto):
        return ahora + timedelta(seconds=5)
    m = re.match(r"^(?:en\s+)?([\d.]+)\s+(segundos?|minutos?|horas?|min|h|s|m)\b", texto)
    if m:
        n = float(m.group(1))
        unidad = m.group(2)[:1]
        if unidad == "s":
            return ahora + timedelta(seconds=n)
        if unidad == "m":
            return ahora + timedelta(minutes=n)
        return ahora + timedelta(hours=n)
    relativo_palabras = re.match(
        r"^(?:en\s+)?((?:media|un|una|uno|unos|unas|[a-z]+)\s+(?:hora|horas|minuto|minutos|segundo|segundos))\b",
        texto,
    )
    if relativo_palabras:
        expr = _numeros_a_digitos(relativo_palabras.group(1))
        return parsear_hora("en " + expr, ahora)
    iso = re.search(
        r"(\d{4})-(\d{2})-(\d{2})[t ](\d{1,2}):(\d{2})(?::(\d{2}))?", texto
    )
    if iso:
        try:
            anio, mes, d = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
            hh, mm = int(iso.group(4)), int(iso.group(5))
            ss = int(iso.group(6) or 0)
            return datetime(anio, mes, d, hh, mm, ss)
        except ValueError:
            return None
    dia = ahora.date()
    if "mañana" in texto or "manana" in texto:
        dia = dia + timedelta(days=1)
    hm = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", texto)
    if hm:
        hh, mm = int(hm.group(1)), int(hm.group(2))
        ss = int(hm.group(3) or 0)
        if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
            return None
        dt = datetime(dia.year, dia.month, dia.day, hh, mm, ss)
        if "mañana" not in texto and dt <= ahora and re.match(r"^\d{1,2}:", texto):
            dt = dt + timedelta(days=1)
        return dt
    return None


EXP_EXPRESION_HORA = [
    re.compile(r"\d{4}-\d{2}-\d{2}[t ]\d{1,2}:\d{2}(?::\d{2})?"),
    re.compile(r"en\s+(?:media\s+hora|una\s+hora|un\s+minuto|\d+(?:\.\d+)?\s+(?:segundos?|minutos?|horas?|min|h|s|m))"),
    re.compile(r"mañana\s+(?:a\s+las\s+)?\d{1,2}:\d{2}"),
    re.compile(r"hoy\s+(?:a\s+las\s+)?\d{1,2}:\d{2}"),
    re.compile(r"a\s+las\s+\d{1,2}:\d{2}(?::\d{2})?"),
    re.compile(r"\d{1,2}:\d{2}(?::\d{2})?"),
    re.compile(r"now|ahora|ahorita|enseguida"),
]


def extraer_expresion_hora(texto):
    """Busca la expresión temporal dentro de una frase completa. Devuelve
    (expresion_hora, resto_texto) o (None, texto_original)."""
    t = (texto or "").lower()
    for patron in EXP_EXPRESION_HORA:
        m = patron.search(t)
        if m:
            expr = m.group(0)
            resto = (t[: m.start()] + t[m.end():]).strip(" .,;:¿¡!?()")
            for verbo in (
                "avisame", "avísame", "avísarme", "recuerdame", "recuérdame",
                "recuérdamelo", "recordame", "recordáme", "quiero que me avises",
                "quiero que recuerdes", "quiero que", "ponme", "pon",
            ):
                if resto.startswith(verbo):
                    resto = resto[len(verbo):]
                    break
            for conector in (" para", " que", " a las", " de"):
                if resto.startswith(conector):
                    resto = resto[len(conector):]
                    break
            resto = resto.strip(" .,;:¿¡!?()").strip()
            if resto.endswith((" para", " que", " recordarme", " avísame")):
                resto = resto.rsplit(" ", 1)[0].strip()
            return expr, resto
    return None, t


def agregar(texto, hora=None, ahora=None):
    texto = (texto or "").strip()
    if not texto:
        return "Error: falta el texto del recordatorio."
    ahora_real = ahora or datetime.now()
    expr, resto = extraer_expresion_hora(texto)
    if expr and parsear_hora(expr, ahora_real) is not None:
        hora, texto = expr, resto
    if not hora:
        return (
            "Error: no encuentro ningún momento en el pedido. "
            "Ejemplos que sí entiendo: 'en 30 segundos', 'a las 15:30', 'en una hora'."
        )
    if not texto:
        texto = "Recordatorio"
    dt = parsear_hora(hora, ahora_real)
    if dt is None:
        return (
            "Error: no entendí la hora. Usa formato 'YYYY-MM-DD HH:MM', 'HH:MM' "
            "o relativo como 'en 20 minutos'."
        )
    if dt <= ahora_real + timedelta(seconds=2):
        return (
            f"Error: la hora {dt.strftime('%Y-%m-%d %H:%M')} ya pasó (ahora es "
            f"{ahora_real.strftime('%Y-%m-%d %H:%M')}). Usa la herramienta "
            "'hora_actual' para calcular bien y vuelve a llamar a agregar_recordatorio."
        )
    lista = cargar()
    lista.append({"texto": texto, "hora": _formatear(dt), "hecho": False})
    guardar(lista)
    return (
        f"Recordatorio programado (#{len(lista)}): '{texto}' para el "
        f"{dt.strftime('%d/%m/%Y %H:%M')}. Te avisaré a esa hora."
    )


def listar():
    lista = cargar()
    if not lista:
        return "No tienes recordatorios programados."
    lineas = []
    for i, r in enumerate(lista, 1):
        estado = "[x]" if r.get("hecho") else "[ ]"
        try:
            fecha = datetime.strptime(r["hora"], "%Y-%m-%d %H:%M:%S").strftime(
                "%d/%m/%Y %H:%M"
            )
        except Exception:
            fecha = r.get("hora", "?")
        lineas.append(f"{i}. {estado} {r.get('texto', '')} ({fecha})")
    return "\n".join(lineas)


def borrar(indice):
    try:
        idx = int(indice) - 1
    except (TypeError, ValueError):
        return "Error: índice inválido."
    lista = cargar()
    if idx < 0 or idx >= len(lista):
        return f"Error: no existe el recordatorio número {indice}."
    texto = lista.pop(idx)["texto"]
    guardar(lista)
    return f"Recordatorio eliminado: {texto}"


def vencidos(ahora=None, max_atraso_minutos=120):
    """Devuelve (y marca como hechos) los recordatorios pendientes cuya hora ya pasó.
    Solo dispara los que llevan como mucho `max_atraso_minutos` de retraso,
    para evitar saltos viejos al reabrir la app."""
    ahora = ahora or datetime.now()
    lista = cargar()
    disparados = []
    resto = []
    for r in lista:
        if r.get("hecho"):
            resto.append(r)
            continue
        try:
            dt = datetime.strptime(r["hora"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            resto.append(r)
            continue
        atraso = (ahora - dt).total_seconds() / 60.0
        if 0 <= atraso <= max_atraso_minutos:
            r["hecho"] = True
            disparados.append(r)
        resto.append(r)
    if disparados:
        guardar(resto)
    return disparados