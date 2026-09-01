# Tools web: búsqueda en internet y traducción.
from utilidades_compartidas import (
    buscar_en_internet_impl,
    copiar_portapapeles_windows,
    normalizar_idioma,
    traducir_impl,
)
import tools.registro as reg


@reg.registrar(
    "buscar_en_internet",
    descripcion="Busca información en internet y devuelve un resumen de los resultados más relevantes.",
    parametros={"consulta": {"type": "string", "description": "La consulta de búsqueda a realizar.", "requerido": True}},
)
def buscar(consulta):
    if not consulta:
        return "Error: falta la consulta de búsqueda."
    return buscar_en_internet_impl(consulta)


@reg.registrar(
    "traducir",
    descripcion="Traduce un texto a otro idioma con un servicio web gratuito y copia el resultado al portapapeles. Ej: traducir 'Hello world' del inglés al español.",
    parametros={
        "texto": {"type": "string", "description": "El texto a traducir.", "requerido": True},
        "idioma_origen": {"type": "string", "description": "Idioma de origen ('es', 'en', ... o 'autodetect')."},
        "idioma_destino": {"type": "string", "description": "Idioma de destino ('es', 'en', ...).", "requerido": True},
    },
)
def traducir(texto, idioma_origen="autodetect", idioma_destino=""):
    texto = (texto or "").strip()
    destino = normalizar_idioma(idioma_destino)
    origen = normalizar_idioma(idioma_origen or "autodetect")
    if not texto:
        return "Error: falta el texto a traducir."
    if len(texto) > 500:
        return "Error: el texto es demasiado largo (máximo 500 caracteres)."
    traduccion = traducir_impl(texto, origen, destino)
    if traduccion.startswith("Error"):
        return traduccion
    try:
        copiar_portapapeles_windows(traduccion)
        return f"Traducción ({origen} -> {destino}):\n{traduccion}\n\n(Copiado al portapapeles)"
    except Exception as e:
        return f"Traducción ({origen} -> {destino}):\n{traduccion}\n\n(No se pudo copiar: {e})"
