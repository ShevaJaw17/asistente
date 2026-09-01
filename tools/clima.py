# Tool de clima: consulta el tiempo actual y pronóstico corto de una ciudad
# usando la API gratuita de Open-Meteo (sin clave). Geocodifica el nombre de la
# ciudad a coordenadas y luego consulta el pronóstico.
from utilidades_compartidas import CLIENTE_WEB
import tools.registro as reg

GEO_API = "https://geocoding-api.open-meteo.com/v1/search"
FORE_API = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO (Weather.WMO) -> descripción en español.
_WMO = {
    0: "cielo despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna ligera",
    53: "llovizna",
    55: "llovizna intensa",
    56: "llovizna helada ligera",
    57: "llovizna helada intensa",
    61: "lluvia ligera",
    63: "lluvia",
    65: "lluvia fuerte",
    66: "lluvia helada ligera",
    67: "lluvia helada intensa",
    71: "nevada ligera",
    73: "nevada",
    75: "nevada fuerte",
    77: "granos de nieve",
    80: "chubascos ligeros",
    81: "chubascos",
    82: "chubascos violentos",
    85: "chubascos de nieve ligeros",
    86: "chubascos de nieve fuertes",
    95: "tormenta",
    96: "tormenta con granizo ligero",
    99: "tormenta con granizo fuerte",
}


def _wikcionario_emojis(codigo):
    """Emoji representativo por código WMO (para amenizar la respuesta)."""
    if codigo < 3:
        return "☀️"
    if codigo == 3 or 45 <= codigo <= 48:
        return "☁️"
    if 51 <= codigo <= 67:
        return "🌧️"
    if 71 <= codigo <= 86:
        return "❄️"
    if codigo >= 95:
        return "⛈️"
    return "🌤️"


def _desc(codigo):
    return _WMO.get(codigo, "condiciones no determinadas")


def _geo(ciudad):
    try:
        resp = CLIENTE_WEB.get(
            GEO_API,
            params={"name": ciudad, "count": 1, "language": "es"},
        )
        resp.raise_for_status()
        datos = resp.json()
        resultados = datos.get("results")
        if not resultados:
            return None, f"No encontré la ciudad '{ciudad}'. Verifica el nombre."
        r = resultados[0]
        nombre = r.get("name", ciudad)
        pais = r.get("country", "")
        admin = r.get("admin1", "")
        ubicacion = nombre
        if admin and admin != nombre:
            ubicacion += f", {admin}"
        if pais:
            ubicacion += f", {pais}"
        return (r["latitude"], r["longitude"], ubicacion), None
    except Exception as e:
        return None, f"Error consultando la ciudad: {e}"


def clima(ciudad):
    """Devuelve el clima actual y pronóstico de 3 días para una ciudad."""
    ciudad = (ciudad or "").strip()
    if not ciudad:
        return "Error: dime de qué ciudad quieres el clima."
    geo, error = _geo(ciudad)
    if error or not geo:
        return error or "No se pudo localizar la ciudad."
    lat, lon, ubicacion = geo
    try:
        resp = CLIENTE_WEB.get(
            FORE_API,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 3,
            },
        )
        resp.raise_for_status()
        d = resp.json()
    except Exception as e:
        return f"Error consultando el clima: {e}"

    cur = d.get("current", {})
    temp = cur.get("temperature_2m")
    cod = cur.get("weather_code", -1)
    viento = cur.get("wind_speed_10m")
    humedad = cur.get("relative_humidity_2m")
    unidad_t = d.get("current_units", {}).get("temperature_2m", "°C")
    unidad_v = d.get("current_units", {}).get("wind_speed_10m", "km/h")

    lineas = [
        f"Clima en {ubicacion} ahora: {_desc(cod)} {_wikcionario_emojis(cod)}.",
    ]
    if temp is not None:
        lineas.append(f"Temperatura: {temp}{unidad_t}.")
    if humedad is not None:
        lineas.append(f"Humedad: {humedad}%.")
    if viento is not None:
        lineas.append(f"Viento: {viento} {unidad_v}.")

    dias = d.get("daily", {})
    tiempos = dias.get("time", [])
    maximos = dias.get("temperature_2m_max", [])
    minimos = dias.get("temperature_2m_min", [])
    codigos = dias.get("weather_code", [])
    if tiempos:
        pronostico = []
        for i, fecha in enumerate(tiempos[:3]):
            etiqueta = "Hoy" if i == 0 else ("Mañana" if i == 1 else "Pasado mañana")
            cod_d = codigos[i] if i < len(codigos) else -1
            try:
                max_d = maximos[i] if i < len(maximos) else None
                min_d = minimos[i] if i < len(minimos) else None
            except IndexError:
                max_d = min_d = None
            parte = f"{etiqueta}: {_desc(cod_d)}"
            if min_d is not None and max_d is not None:
                parte += f", {min_d}–{max_d}°C"
            pronostico.append(parte)
        lineas.append("Pronóstico: " + " | ".join(pronostico) + ".")

    return "\n".join(lineas)


@reg.registrar(
    "clima",
    descripcion=(
        "Consulta el clima actual y el pronóstico de 3 días de una ciudad. "
        "Ej: '¿qué tiempo hace en Madrid?'. Devuelve temperatura, estado del cielo, "
        "humedad, viento y el pronóstico."
    ),
    parametros={
        "ciudad": {"type": "string", "description": "Nombre de la ciudad (ej. 'Madrid', 'Buenos Aires', 'Lima').", "requerido": True}
    },
)
def tool_clima(ciudad):
    return clima(ciudad)
