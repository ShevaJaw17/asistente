# Tools de archivos: listar, leer, buscar y resumir (el resumen usa el modelo).
import os

import tools.registro as reg


@reg.registrar(
    "listar_archivos",
    descripcion="Lista los archivos y carpetas de un directorio.",
    parametros={"ruta": {"type": "string", "description": "Ruta del directorio (por defecto el actual)."}},
)
def listar(ruta="."):
    ruta = ruta or "."
    try:
        items = os.listdir(ruta)
        return "\n".join(items) if items else "(directorio vacío)"
    except FileNotFoundError:
        return f"Error: no existe la ruta {ruta}"
    except PermissionError:
        return f"Error: sin permisos para {ruta}"


@reg.registrar(
    "leer_archivo",
    descripcion="Lee el contenido de un archivo de texto.",
    parametros={"ruta": {"type": "string", "description": "Ruta absoluta del archivo.", "requerido": True}},
)
def leer(ruta):
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.read()
        return contenido[:3000] if len(contenido) > 3000 else contenido
    except FileNotFoundError:
        return f"Error: no existe el archivo {ruta}"
    except Exception as e:
        return f"Error al leer el archivo: {e}"


@reg.registrar(
    "buscar_archivos",
    descripcion="Busca archivos o carpetas por nombre en un directorio (y subcarpetas) del disco.",
    parametros={
        "nombre": {"type": "string", "description": "Nombre (o parte) del archivo o carpeta a buscar.", "requerido": True},
        "ruta": {"type": "string", "description": "Directorio donde comenzar (por defecto el usuario)."},
        "max_resultados": {"type": "integer", "description": "Máximo de resultados (por defecto 20)."},
    },
)
def buscar(nombre, ruta=None, max_resultados=20):
    termino = (nombre or "").lower()
    ruta = ruta or os.path.expanduser("~")
    try:
        max_res = int(max_resultados)
    except (TypeError, ValueError):
        max_res = 20
    if not termino:
        return "Error: falta el nombre a buscar."
    encontrados = []
    try:
        for raiz, dirs, archivos in os.walk(ruta):
            for item in dirs + archivos:
                if len(encontrados) >= max_res:
                    break
                if termino in item.lower():
                    encontrados.append(os.path.join(raiz, item))
    except Exception as e:
        return f"Error buscando: {e}"
    if not encontrados:
        return f"No se encontraron elementos con '{termino}' en {ruta}."
    return "\n".join(encontrados[:max_res])


@reg.registrar(
    "resumir_archivo",
    descripcion="Lee un archivo de texto y devuelve un resumen en español generado por el modelo.",
    parametros={"ruta": {"type": "string", "description": "Ruta absoluta del archivo a resumir.", "requerido": True}},
)
def resumir(ruta):
    if not ruta:
        return "Error: falta la ruta del archivo."
    # Import perezoso: evita dependencia circular en tiempo de import.
    import asistente
    return asistente.resumir_archivo_impl(ruta)
