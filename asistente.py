# Asistente Virtual Local - llama.cpp (Vulkan/GPU)
# Lanzador: haz doble clic en "iniciar.bat"
import json
import os
import re
import subprocess
import urllib.parse
import webbrowser
from datetime import datetime

import httpx

import recordatorios
import sistema

SERVIDOR = "http://127.0.0.1:8080"
MODELO = "qwen2.5-7b"


def copiar_portapapeles_windows(texto):
    import ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    data = texto.encode("utf-16-le") + b"\x00\x00"

    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    user32.OpenClipboard(None)
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            raise OSError("GlobalAlloc devolvió NULL")
        p = kernel32.GlobalLock(h)
        if not p:
            raise OSError("GlobalLock devolvió NULL")
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        ctypes.memmove(p, buf, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()


# Función de confirmación configurable (la GUI la sobrescribe para mostrar un diálogo)
confirmar_accion = None


def pedir_confirmacion(mensaje):
    if confirmar_accion is not None:
        return confirmar_accion(mensaje)
    try:
        respuesta = input(f"[Confirmación requerida] {mensaje} (s/n): ").strip().lower()
        return respuesta in ("s", "si", "yes", "y", "sí")
    except (EOFError, KeyboardInterrupt):
        return False
CLIENTE = httpx.Client(base_url=SERVIDOR, timeout=httpx.Timeout(300.0))

DIRECTORIO_PROYECTO = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_MEMORIA = os.path.join(DIRECTORIO_PROYECTO, "memoria.json")
ARCHIVO_TAREAS = os.path.join(DIRECTORIO_PROYECTO, "tareas.json")
ARCHIVO_NOTAS = os.path.join(DIRECTORIO_PROYECTO, "notas.json")
CLIENTE_WEB = httpx.Client(timeout=httpx.Timeout(20.0), headers={"User-Agent": "Mozilla/5.0"})


def cargar_tareas():
    if os.path.exists(ARCHIVO_TAREAS):
        try:
            with open(ARCHIVO_TAREAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_tareas(tareas):
    with open(ARCHIVO_TAREAS, "w", encoding="utf-8") as f:
        json.dump(tareas, f, ensure_ascii=False, indent=2)


def cargar_notas():
    if os.path.exists(ARCHIVO_NOTAS):
        try:
            with open(ARCHIVO_NOTAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_notas(notas):
    with open(ARCHIVO_NOTAS, "w", encoding="utf-8") as f:
        json.dump(notas, f, ensure_ascii=False, indent=2)


def cargar_memoria():
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_memoria(memoria):
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)


ARCHIVO_HISTORIAL = os.path.join(DIRECTORIO_PROYECTO, "historial.json")


def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
        except Exception:
            pass
    return []


def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def guardar_intercambio(mensajes, limite=200):
    """Guarda el último intercambio usuario -> asistente en historial.json."""
    try:
        turno = {"ts": "", "usuario": "", "asistente": ""}
        for m in mensajes[-8:]:
            if m.get("role") == "user" and not m.get("tool_calls"):
                if m.get("content"):
                    turno["usuario"] = m["content"]
            elif m.get("role") == "assistant" and not m.get("tool_calls"):
                if m.get("content"):
                    turno["asistente"] = m["content"]
        if not (turno["usuario"] or turno["asistente"]):
            return
        turno["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        historial = cargar_historial()
        historial.append(turno)
        guardar_historial(historial[-limite:])
    except Exception:
        pass


def buscar_en_internet_impl(consulta):
    url = "https://html.duckduckgo.com/html/"
    try:
        resp = CLIENTE_WEB.post(url, data={"q": consulta})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return f"Error al buscar en internet: {e}"
    bloques = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    if not bloques:
        return "No se encontraron resultados."
    resultados = []
    for href, titulo in bloques[:6]:
        if "uddg=" in href:
            href = urllib.parse.unquote(
                re.search(r"uddg=([^&]+)", href).group(1)
            )
        titulo_limpio = re.sub(r"<[^>]+>", "", titulo).strip()
        resultados.append(f"- {titulo_limpio}\n  {href}")
    return "\n".join(resultados)


def normalizar_idioma(idioma):
    idioma = str(idioma or "").strip().lower()
    equivalencias = {
        "es": "es", "español": "es", "espanol": "es", "castellano": "es",
        "en": "en", "inglés": "en", "ingles": "en", "english": "en",
        "fr": "fr", "francés": "fr", "frances": "fr", "français": "fr",
        "de": "de", "alemán": "de", "aleman": "de",
        "it": "it", "italiano": "it",
        "pt": "pt", "portugués": "pt", "portugues": "pt",
        "ja": "ja", "japonés": "ja", "japones": "ja",
        "zh": "zh", "chino": "zh", "chino simplificado": "zh",
        "ko": "ko", "coreano": "ko",
        "ru": "ru", "ruso": "ru",
        "ar": "ar", "árabe": "ar", "arabe": "ar",
    }
    if idioma in ("auto", "autodetect", "detectar"):
        return "autodetect"
    return equivalencias.get(idioma, idioma)


def traducir_impl(texto, origen, destino):
    try:
        resp = CLIENTE_WEB.get(
            "https://api.mymemory.translated.net/get",
            params={
                "q": texto,
                "langpair": f"{origen}|{destino}",
            },
        )
        resp.raise_for_status()
        datos = resp.json()
        traduccion = datos.get("responseData", {}).get("translatedText")
        if not traduccion:
            return "Error: el servicio de traducción no devolvió resultado."
        return traduccion
    except Exception as e:
        return f"Error al traducir: {e}"


def resumir_archivo_impl(ruta):
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.read()
    except FileNotFoundError:
        return f"Error: no existe el archivo {ruta}"
    except Exception as e:
        return f"Error al leer el archivo: {e}"
    if not contenido.strip():
        return "El archivo está vacío."
    contenido = contenido[:12000]
    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres un asistente que resume documentos en español. Devuelve únicamente "
                "el resumen en español: claro, breve y con un máximo de 8 frases."
            ),
        },
        {"role": "user", "content": f"Resume este texto:\n\n{contenido}"},
    ]
    try:
        data = llamar_modelo(mensajes)
        return data["choices"][0]["message"].get("content", "(sin respuesta)")
    except Exception as e:
        return f"Error al generar el resumen: {e}"


HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "hora_actual",
            "description": "Devuelve la fecha y hora actual del sistema.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "info_del_sistema",
            "description": "Devuelve información básica del sistema operativo.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_archivos",
            "description": "Lista los archivos y carpetas de un directorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta del directorio a listar (por defecto el directorio actual).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leer_archivo",
            "description": "Lee el contenido de un archivo de texto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta absoluta del archivo a leer.",
                    }
                },
                "required": ["ruta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculadora",
            "description": "Evalúa una expresión matemática simple y devuelve el resultado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expresion": {
                        "type": "string",
                        "description": "Expresión matemática a evaluar, ej. '2+3*4'.",
                    }
                },
                "required": ["expresion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_archivos",
            "description": "Busca archivos o carpetas por nombre en un directorio (y sus subcarpetas) del disco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {
                        "type": "string",
                        "description": "Nombre (o parte del nombre) del archivo o carpeta a buscar.",
                    },
                    "ruta": {
                        "type": "string",
                        "description": "Directorio donde comenzar la búsqueda (por defecto el directorio del usuario).",
                    },
                    "max_resultados": {
                        "type": "integer",
                        "description": "Máximo de resultados a devolver (por defecto 20).",
                    },
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_en_internet",
            "description": "Busca información en internet y devuelve un resumen de los resultados más relevantes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": "La consulta de búsqueda a realizar.",
                    }
                },
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recordar",
            "description": "Guarda en memoria una preferencia o dato que el usuario pide recordar para el futuro. Ej: 'recuerda que me llamo Juan', 'recuerda que odio el café'. Devuelve lo guardado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clave": {
                        "type": "string",
                        "description": "Etiqueta corta para identificar el dato (ej. 'nombre', 'gusto', 'titulo').",
                    },
                    "valor": {
                        "type": "string",
                        "description": "El dato o preferencia a recordar.",
                    },
                },
                "required": ["clave", "valor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "que_recuerdas",
            "description": "Devuelve todas las preferencias y datos que el asistente tiene guardados en memoria.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "olvidar",
            "description": "Elimina de la memoria un dato guardado previamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clave": {
                        "type": "string",
                        "description": "La clave del dato que se desea olvidar.",
                    }
                },
                "required": ["clave"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_tarea",
            "description": "Añade una nueva tarea a la lista de pendientes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tarea": {
                        "type": "string",
                        "description": "La descripción de la tarea a añadir.",
                    }
                },
                "required": ["tarea"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_tareas",
            "description": "Muestra la lista de tareas pendientes y completadas.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "completar_tarea",
            "description": "Marca una tarea de la lista como completada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {
                        "type": "integer",
                        "description": "El número de la tarea a marcar como completada (según su posición en la lista).",
                    }
                },
                "required": ["indice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "borrar_tarea",
            "description": "Elimina una tarea de la lista de pendientes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {
                        "type": "integer",
                        "description": "El número de la tarea a eliminar.",
                    }
                },
                "required": ["indice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_elemento",
            "description": "Abre un archivo, aplicación o carpeta del sistema usando su programa asociado. Ej: 'notepad', 'calc', o una ruta a un .txt, .pdf o carpeta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta del archivo, nombre del programa o carpeta a abrir.",
                    }
                },
                "required": ["ruta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_url",
            "description": "Abre una URL en el navegador web predeterminado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "La URL o sitio web a abrir, ej. 'https://www.youtube.com'.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copiar_portapapeles",
            "description": "Copia un texto al portapapeles del sistema para que el usuario pueda pegarlo donde quiera (Ctrl+V).",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "El texto a copiar al portapapeles.",
                    }
                },
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ejecutar_comando",
            "description": "Ejecuta un comando del sistema (cmd). Pide confirmación al usuario antes de ejecutarlo. Úsalo para tareas como 'dir', 'ipconfig', crear carpetas, abrir programas, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "comando": {
                        "type": "string",
                        "description": "El comando a ejecutar.",
                    }
                },
                "required": ["comando"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_nota",
            "description": "Guarda una nota rápida o idea con su fecha, como un diario acumulativo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "El contenido de la nota o idea.",
                    }
                },
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_notas",
            "description": "Muestra todas las notas guardadas, de la más reciente a la más antigua.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "borrar_nota",
            "description": "Elimina una nota guardada por su número de lista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {
                        "type": "integer",
                        "description": "El número de la nota a eliminar (según listar_notas).",
                    }
                },
                "required": ["indice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traducir",
            "description": "Traduce un texto a otro idioma con un servicio web gratuito y copia el resultado al portapapeles automáticamente. Ej: traducir 'Hello world' del inglés al español.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "El texto a traducir.",
                    },
                    "idioma_origen": {
                        "type": "string",
                        "description": "Idioma de origen ('es', 'en', 'fr', 'de', 'it', 'pt', 'ja', 'zh', 'ko', 'ru' o 'autodetect').",
                    },
                    "idioma_destino": {
                        "type": "string",
                        "description": "Idioma de destino ('es', 'en', 'fr', 'de', 'it', 'pt', 'ja', 'zh', 'ko', 'ru').",
                    },
                },
                "required": ["texto", "idioma_destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumir_archivo",
            "description": "Lee un archivo de texto y devuelve un resumen en español generado por el modelo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta absoluta del archivo a resumir.",
                    }
                },
                "required": ["ruta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_recordatorio",
            "description": "Programa un recordatorio con fecha y hora para avisar al usuario. En 'texto' pon LITERALMENTE todo lo que pidió el usuario, incluyendo el momento ('recuérdame tomar agua en 30 segundos', 'avísame a las 15:30 para la reunión', 'recuérdame bailar en una hora'). El sistema extrae la hora automáticamente; no inventes fechas ni conviertas horas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "La petición completa del usuario, tal cual, con el momento incluido.",
                    },
                    "hora": {
                        "type": "string",
                        "description": "Opcional. Solo úsala si es imprescindible; si la usas pon una expresión de tiempo ('en 30 segundos', '15:30', '2026-08-29 15:30').",
                    },
                },
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_recordatorios",
            "description": "Muestra todos los recordatorios programados con su estado y hora.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "borrar_recordatorio",
            "description": "Elimina un recordatorio por el número que muestra listar_recordatorios.",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {
                        "type": "integer",
                        "description": "Número del recordatorio a eliminar (según listar_recordatorios).",
                    }
                },
                "required": ["indice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ajustar_volumen",
            "description": "Ajusta el volumen maestro del sistema a un porcentaje (0-100). Ej: 'sube el volumen a 60', 'pon el volumen al máximo'. Para subir o bajar poco a poco usa el número exacto que quieres dejar, no 'un poco'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nivel": {
                        "type": "integer",
                        "description": "Porcentaje de volumen a dejar, de 0 a 100.",
                    }
                },
                "required": ["nivel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capturar_pantalla",
            "description": "Toma una captura de pantalla completa, la guarda en la carpeta 'capturas' y la abre para que el usuario la vea.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "limpiar_archivos_temporales",
            "description": "Borra los archivos temporales de %TEMP% más antiguos de ciertos días (por defecto 7). Libera espacio. Pide confirmación al usuario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dias": {
                        "type": "integer",
                        "description": "Edad mínima en días de los archivos a borrar (por defecto 7).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vaciar_papelera",
            "description": "Vacia la papelera de reciclaje del sistema por completo. Pide confirmación al usuario.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def ejecutar_herramienta(nombre, argumentos):
    if nombre == "hora_actual":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if nombre == "info_del_sistema":
        return f"Sistema: {os.name}, procesadores: {os.cpu_count()}"
    if nombre == "listar_archivos":
        ruta = argumentos.get("ruta") or "."
        try:
            items = os.listdir(ruta)
            return "\n".join(items) if items else "(directorio vacío)"
        except FileNotFoundError:
            return f"Error: no existe la ruta {ruta}"
        except PermissionError:
            return f"Error: sin permisos para {ruta}"
    if nombre == "leer_archivo":
        ruta = argumentos.get("ruta")
        try:
            with open(ruta, "r", encoding="utf-8", errors="replace") as f:
                contenido = f.read()
            return contenido[:3000] if len(contenido) > 3000 else contenido
        except FileNotFoundError:
            return f"Error: no existe el archivo {ruta}"
        except Exception as e:
            return f"Error al leer el archivo: {e}"
    if nombre == "calculadora":
        try:
            permitidos = set("0123456789+-*/(). ")
            expresion = argumentos.get("expresion", "0")
            if not all(c in permitidos for c in expresion):
                return "Error: la expresión contiene caracteres no permitidos"
            resultado = eval(expresion, {"__builtins__": {}}, {})
            return str(resultado)
        except Exception as e:
            return f"Error evaluando la expresión: {e}"
    if nombre == "buscar_archivos":
        termino = (argumentos.get("nombre") or "").lower()
        ruta = argumentos.get("ruta") or os.path.expanduser("~")
        max_res = int(argumentos.get("max_resultados") or 20)
        if not termino:
            return "Error: falta el nombre a buscar."
        encontrados = []
        try:
            for raiz, dirs, archivos in os.walk(ruta):
                if len(encontrados) >= max_res:
                    break
                for item in dirs + archivos:
                    if termino in item.lower():
                        encontrados.append(os.path.join(raiz, item))
                        if len(encontrados) >= max_res:
                            break
        except Exception as e:
            return f"Error buscando: {e}"
        if not encontrados:
            return f"No se encontraron elementos con '{termino}' en {ruta}."
        return "\n".join(encontrados)
    if nombre == "buscar_en_internet":
        consulta = argumentos.get("consulta")
        if not consulta:
            return "Error: falta la consulta de búsqueda."
        return buscar_en_internet_impl(consulta)
    if nombre == "recordar":
        clave = (argumentos.get("clave") or "").strip().lower()
        valor = (argumentos.get("valor") or "").strip()
        if not clave or not valor:
            return "Error: faltan clave o valor."
        memoria = cargar_memoria()
        memoria[clave] = valor
        guardar_memoria(memoria)
        return f"Recordado: {clave} = {valor}"
    if nombre == "que_recuerdas":
        memoria = cargar_memoria()
        if not memoria:
            return "No tengo nada guardado en memoria."
        return "\n".join(f"- {k}: {v}" for k, v in memoria.items())
    if nombre == "olvidar":
        clave = (argumentos.get("clave") or "").strip().lower()
        memoria = cargar_memoria()
        if clave in memoria:
            del memoria[clave]
            guardar_memoria(memoria)
            return f"Olvidado: {clave}"
        return f"No hay nada guardado con la clave '{clave}'."
    if nombre == "agregar_tarea":
        tarea = (argumentos.get("tarea") or "").strip()
        if not tarea:
            return "Error: falta la descripción de la tarea."
        tareas = cargar_tareas()
        tareas.append({"texto": tarea, "completada": False})
        guardar_tareas(tareas)
        return f"Tarea añadida en la posición {len(tareas)}: {tarea}"
    if nombre == "listar_tareas":
        tareas = cargar_tareas()
        if not tareas:
            return "La lista de tareas está vacía."
        lineas = []
        for i, t in enumerate(tareas, 1):
            estado = "[x]" if t.get("completada") else "[ ]"
            lineas.append(f"{i}. {estado} {t['texto']}")
        return "\n".join(lineas)
    if nombre == "completar_tarea" or nombre == "borrar_tarea":
        indice = argumentos.get("indice")
        try:
            indice = int(indice)
        except (TypeError, ValueError):
            return "Error: índice inválido."
        tareas = cargar_tareas()
        if indice < 1 or indice > len(tareas):
            return f"Error: no existe la tarea número {indice}."
        if nombre == "completar_tarea":
            tareas[indice - 1]["completada"] = True
            guardar_tareas(tareas)
            return f"Tarea {indice} completada: {tareas[indice - 1]['texto']}"
        else:
            tarea_borrada = tareas.pop(indice - 1)
            guardar_tareas(tareas)
            return f"Tarea eliminada: {tarea_borrada['texto']}"
    if nombre == "abrir_elemento":
        ruta = (argumentos.get("ruta") or "").strip()
        if not ruta:
            return "Error: falta la ruta o el programa a abrir."
        try:
            os.startfile(ruta)
            return f"Abierto: {ruta}"
        except FileNotFoundError:
            return f"Error: no se encontró '{ruta}'."
        except Exception as e:
            return f"Error al abrir: {e}"
    if nombre == "abrir_url":
        url = (argumentos.get("url") or "").strip()
        if not url:
            return "Error: falta la URL."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return f"Abriendo en el navegador: {url}"
        except Exception as e:
            return f"Error al abrir el navegador: {e}"
    if nombre == "copiar_portapapeles":
        texto = argumentos.get("texto") or ""
        if not texto:
            return "Error: falta el texto a copiar."
        try:
            copiar_portapapeles_windows(texto)
            return f"Copiado al portapapeles: {texto[:80]}"
        except Exception as e:
            return f"Error al copiar al portapapeles: {e}"
    if nombre == "ejecutar_comando":
        comando = (argumentos.get("comando") or "").strip()
        if not comando:
            return "Error: falta el comando a ejecutar."
        if not pedir_confirmacion(comando):
            return "Comando cancelado por el usuario."
        try:
            resultado = subprocess.run(
                comando,
                shell=True,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=60,
            )
            salida = resultado.stdout.strip()
            if resultado.stderr.strip():
                salida += ("\n" if salida else "") + resultado.stderr.strip()
            return salida if salida else f"Comando ejecutado correctamente (código {resultado.returncode})."
        except subprocess.TimeoutExpired:
            return "Error: el comando tardó más de 60 segundos y fue cancelado."
        except Exception as e:
            return f"Error al ejecutar el comando: {e}"
    if nombre == "agregar_nota":
        texto = (argumentos.get("texto") or "").strip()
        if not texto:
            return "Error: falta el texto de la nota."
        notas = cargar_notas()
        nota = {"texto": texto, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")}
        notas.append(nota)
        guardar_notas(notas)
        return f"Nota guardada (nº {len(notas)}): {texto}"
    if nombre == "listar_notas":
        notas = cargar_notas()
        if not notas:
            return "No tienes ninguna nota guardada."
        lineas = []
        for i, n in enumerate(reversed(notas), 1):
            lineas.append(f"{i}. [{n.get('fecha', '?')}] {n['texto']}")
        return "\n".join(lineas)
    if nombre == "borrar_nota":
        indice = argumentos.get("indice")
        try:
            indice = int(indice)
        except (TypeError, ValueError):
            return "Error: índice inválido."
        notas = cargar_notas()
        if indice < 1 or indice > len(notas):
            return f"Error: no existe la nota número {indice}."
        nota_borrada = notas.pop(indice - 1)
        guardar_notas(notas)
        return f"Nota eliminada: {nota_borrada['texto']}"
    if nombre == "traducir":
        texto = (argumentos.get("texto") or "").strip()
        destino = normalizar_idioma(argumentos.get("idioma_destino"))
        origen = normalizar_idioma(argumentos.get("idioma_origen") or "autodetect")
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
            return f"Traducción ({origen} -> {destino}):\n{traduccion}\n\n(No se pudo copiar al portapapeles: {e})"
    if nombre == "resumir_archivo":
        ruta = argumentos.get("ruta")
        if not ruta:
            return "Error: falta la ruta del archivo."
        return resumir_archivo_impl(ruta)
    if nombre == "agregar_recordatorio":
        return recordatorios.agregar(argumentos.get("texto"), argumentos.get("hora"))
    if nombre == "listar_recordatorios":
        return recordatorios.listar()
    if nombre == "borrar_recordatorio":
        return recordatorios.borrar(argumentos.get("indice"))
    if nombre == "ajustar_volumen":
        try:
            nivel = int(argumentos.get("nivel"))
        except (TypeError, ValueError):
            return "Error: 'nivel' debe ser un número del 0 al 100."
        return sistema.ajustar_volumen(nivel)
    if nombre == "capturar_pantalla":
        return sistema.capturar_pantalla()
    if nombre == "limpiar_archivos_temporales":
        dias = argumentos.get("dias") or 7
        try:
            dias = int(dias)
        except (TypeError, ValueError):
            return "Error: 'dias' debe ser un número."
        if not pedir_confirmacion(
            f"¿Puedo borrar los archivos temporales de más de {dias} días? "
            "(libera espacio, no afecta a tus documentos)"
        ):
            return "Limpieza de temporales cancelada por el usuario."
        return sistema.limpiar_temporales(dias)
    if nombre == "vaciar_papelera":
        if not pedir_confirmacion("¿Puedo vaciar la papelera de reciclaje?"):
            return "Vaciar papelera cancelado por el usuario."
        return sistema.vaciar_papelera()
    return f"Herramienta desconocida: {nombre}"


def llamar_modelo(mensajes, herramientas=None):
    payload = {
        "model": MODELO,
        "messages": mensajes,
        "max_tokens": 512,
        "temperature": 0.8,
    }
    if herramientas:
        payload["tools"] = herramientas
    resp = CLIENTE.post("/v1/chat/completions", json=payload)
    resp.raise_for_status()
    return resp.json()


def responder_asistente(mensajes):
    data = llamar_modelo(mensajes, HERRAMIENTAS)
    return data["choices"][0]["message"]


PROMPT_SISTEMA = (
    "Eres Nico Robin, una asistente personal virtual mujer, erudita, elegante y "
    "sarcástica de forma sutil. Tienes una personalidad cálida, culta e inteligente, "
    "con un toque de humor seco y un aire tranquilo y seguro. Hablas en español de forma "
    "natural y cercana, como un amigo informado, no como un robot.\n\n"
    "Modo de hablar:\n"
    "- Usa un tono amigable y humano; tutea al usuario y muestra interés genuino.\n"
    "- Responde con naturalidad: frases conversacionales, no listas perfectas ni "
    "respuestas robóticas.\n"
    "- Cuando no sepas algo o no tengas acceso a la información, dilo con honestidad "
    "y un toque de humor, en lugar de inventar nunca.\n"
    "- Haz preguntas de vuelta cuando tenga sentido, para mantener la conversación viva.\n"
    "- No abrumes con datos: usa lo justo y con claridad, como haría una persona.\n\n"
    "REGLAS OBLIGATORIAS sobre información real y herramientas:\n"
    "1. NUNCA inventes datos que no conoces. Si el usuario pregunta por la hora, la fecha, "
    "información de archivos, del sistema, de internet, tu memoria o cualquier dato externo, "
    "SIEMPRE debes usar la herramienta correspondiente para obtenerlo.\n"
    "2. Si una herramienta falla o no está disponible, dilo con honestidad; no adivines ni fabriques.\n"
    "3. Cuando uses una herramienta, integra el resultado en tu respuesta con total naturalidad, "
    "sin mencionar que usaste una herramienta, una API o que 'consultaste tu base de datos'. "
    "Simplemente di la información como si la supieras.\n"
    "4. No agregues estos puntos de instrucción en tus respuestas; son solo guías internas."
)


def resumen_contexto(historial, max_caracteres=1100):
    """Devuelve fragmento de la charla anterior como contexto, sin repetir el último turno."""
    fragmentos = []
    for t in historial:
        if t.get("usuario"):
            fragmentos.append(f"Usuario: {t['usuario']}")
        if t.get("asistente"):
            fragmentos.append(f"Robin: {t['asistente']}")
    texto = "\n".join(fragmentos)
    if len(texto) > max_caracteres:
        texto = texto[-max_caracteres:]
    return texto


def sistema_con_contexto():
    """PROMPT_SISTEMA + memoria explícita + fragmento de nuestra última conversación."""
    partes = [PROMPT_SISTEMA]
    memoria = cargar_memoria()
    if memoria:
        lineas = "\n".join(f"- {c}: {v}" for c, v in memoria.items())
        partes.append(
            "MEMORIA EXPLÍCITA DEL USUARIO (usa estos datos cuando sean relevantes, "
            "no los repitas sin motivo):\n" + lineas
        )
    historial = cargar_historial()
    ultimos = historial[-8:]
    if ultimos:
        contexto = resumen_contexto(ultimos)
        if contexto:
            partes.append(
                "CONTEXTO DE NUESTRA ÚLTIMA CONVERSACIÓN (útil para continuar con "
                "naturalidad; NO lo repitas literalmente ni saludes de nuevo):\n" + contexto
            )
    return "\n\n---\n\n".join(partes)


def main():
    print("=== Asistente local (qwen2.5-7b / Vulkan-GPU) ===")
    print("Servidor: " + SERVIDOR)
    print("Escribe 'salir' para terminar.")
    print()
    mensajes = [
        {
            "role": "system",
            "content": sistema_con_contexto(),
        }
    ]
    while True:
        try:
            entrada = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Adios.")
            break
        if entrada.lower() in ("salir", "exit", "quit"):
            print("Adios.")
            break
        if not entrada:
            continue
        mensajes.append({"role": "user", "content": entrada})
        try:
            mensaje = responder_asistente(mensajes)
        except Exception as e:
            print(f"\n[Error de conexión con el servidor: {e}]")
            print("Asegúrate de que el servidor llama.cpp esté corriendo (iniciar_servidor.bat).")
            mensajes.pop()
            continue
        mensajes.append({"role": "assistant", "content": mensaje.get("content", ""),
                         "tool_calls": mensaje.get("tool_calls")})
        print()
        if mensaje.get("tool_calls"):
            for llamada in mensaje["tool_calls"]:
                nombre = llamada["function"]["name"]
                args = llamada["function"].get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                print(f"[Ejecutando herramienta: {nombre} {args}]")
                resultado = ejecutar_herramienta(nombre, args)
                mensajes.append(
                    {
                        "role": "tool",
                        "tool_call_id": llamada.get("id", ""),
                        "content": str(resultado),
                    }
                )
            try:
                mensaje = responder_asistente(mensajes)
            except Exception as e:
                print(f"\n[Error: {e}]")
                mensajes.append({"role": "assistant", "content": ""})
                continue
            mensajes.append({"role": "assistant", "content": mensaje.get("content", "")})
        print(f"Asistente: {mensaje.get('content', '')}")
        print()


if __name__ == "__main__":
    main()
