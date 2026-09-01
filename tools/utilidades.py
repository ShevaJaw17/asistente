# Tools de utilidades: hora, info del sistema, calculadora, portapapeles,
# ejecutar comando y abrir elementos/URLs.
import os
import re
import subprocess
import webbrowser
from datetime import datetime

import tools.asistente_util as util
import tools.registro as reg


@reg.registrar(
    "hora_actual",
    descripcion="Devuelve la fecha y hora actual del sistema.",
)
def hora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@reg.registrar(
    "info_del_sistema",
    descripcion="Devuelve información básica del sistema operativo.",
)
def info():
    return f"Sistema: {os.name}, procesadores: {os.cpu_count()}"


@reg.registrar(
    "calculadora",
    descripcion="Evalúa una expresión matemática simple y devuelve el resultado.",
    parametros={"expresion": {"type": "string", "description": "Expresión matemática, ej. '2+3*4'.", "requerido": True}},
)
def calculadora(expresion):
    try:
        permitidos = set("0123456789+-*/(). ")
        expresion = (expresion or "0")
        if not all(c in permitidos for c in expresion):
            return "Error: la expresión contiene caracteres no permitidos"
        return str(eval(expresion, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception as e:
        return f"Error evaluando la expresión: {e}"


@reg.registrar(
    "copiar_portapapeles",
    descripcion="Copia un texto al portapapeles del sistema para que el usuario pueda pegarlo (Ctrl+V).",
    parametros={"texto": {"type": "string", "description": "El texto a copiar.", "requerido": True}},
)
def copiar(texto):
    if not texto:
        return "Error: falta el texto a copiar."
    try:
        from asistente import copiar_portapapeles_windows
        copiar_portapapeles_windows(texto)
        return f"Copiado al portapapeles: {texto[:80]}"
    except Exception as e:
        return f"Error al copiar al portapapeles: {e}"


@reg.registrar(
    "ejecutar_comando",
    descripcion="Ejecuta un comando del sistema (cmd). Pide confirmación al usuario. Úsalo para tareas como 'dir', 'ipconfig', crear carpetas, etc.",
    parametros={"comando": {"type": "string", "description": "El comando a ejecutar.", "requerido": True}},
    requiere_confirmacion=True,
)
def ejecutar(comando):
    comando = (comando or "").strip()
    if not comando:
        return "Error: falta el comando a ejecutar."
    if not util.pedir_confirmacion(comando):
        return "Comando cancelado por el usuario."
    try:
        resultado = subprocess.run(
            comando, shell=True, capture_output=True, text=True,
            errors="replace", timeout=60,
        )
        salida = resultado.stdout.strip()
        if resultado.stderr.strip():
            salida += ("\n" if salida else "") + resultado.stderr.strip()
        return salida if salida else f"Comando ejecutado correctamente (código {resultado.returncode})."
    except subprocess.TimeoutExpired:
        return "Error: el comando tardó más de 60 segundos y fue cancelado."
    except Exception as e:
        return f"Error al ejecutar el comando: {e}"


@reg.registrar(
    "abrir_elemento",
    descripcion="Abre un archivo, aplicación o carpeta del sistema usando su programa asociado. Ej: 'notepad', 'calc', o una ruta.",
    parametros={"ruta": {"type": "string", "description": "Ruta del archivo, nombre del programa o carpeta a abrir.", "requerido": True}},
)
def abrir(ruta):
    ruta = (ruta or "").strip()
    if not ruta:
        return "Error: falta la ruta o el programa a abrir."
    try:
        os.startfile(ruta)
        return f"Abierto: {ruta}"
    except FileNotFoundError:
        return f"Error: no se encontró '{ruta}'."
    except Exception as e:
        return f"Error al abrir: {e}"


@reg.registrar(
    "abrir_url",
    descripcion="Abre una URL en el navegador web predeterminado.",
    parametros={"url": {"type": "string", "description": "La URL o sitio web a abrir.", "requerido": True}},
)
def abrir_url(url):
    url = (url or "").strip()
    if not url:
        return "Error: falta la URL."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"Abriendo en el navegador: {url}"
    except Exception as e:
        return f"Error al abrir el navegador: {e}"
