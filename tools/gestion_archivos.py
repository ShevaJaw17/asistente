# Gestión de archivos automática (rol 'empleado'): organizar por reglas y
# renombrar en masa. Se apoya en os/shutil; pide confirmación antes de mover.
import os
import re
import shutil
from datetime import datetime

import tools.registro as reg
import tools.asistente_util as util

# Categorías por extensión para organizar de forma automática.
_CATEGORIAS = {
    "Imágenes": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"),
    "Documentos": (".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"),
    "Hojas de cálculo": (".xls", ".xlsx", ".csv", ".ods"),
    "Presentaciones": (".ppt", ".pptx", ".odp"),
    "Vídeos": (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"),
    "Audio": (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"),
    "Archivos": (".zip", ".rar", ".7z", ".tar", ".gz"),
    "Programas": (".exe", ".msi", ".bat", ".ps1", ".sh"),
    "Código": (".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".java", ".cpp", ".c"),
}


@reg.registrar(
    "organizar_archivos",
    descripcion="Organiza los archivos de una carpeta moviéndolos a subcarpetas por tipo (Imágenes, Documentos, Vídeos...). Pide confirmación antes de mover.",
    parametros={
        "carpeta": {"type": "string", "description": "Ruta de la carpeta a organizar.", "requerido": True},
        "modo": {"type": "string", "description": "'tipo' (por extensión, por defecto) u 'organizado' (carpetas por tipo)."},
    },
)
def organizar(carpeta, modo="tipo"):
    carpeta = (carpeta or "").strip().strip('"')
    if not os.path.isdir(carpeta):
        return f"Error: no existe la carpeta {carpeta}."
    if not util.pedir_confirmacion(f"¿Organizo los archivos de {carpeta}?"):
        return "Cancelado: no se organizó nada."
    movidos = 0
    lineas = []
    for nombre in os.listdir(carpeta):
        origen = os.path.join(carpeta, nombre)
        if os.path.isdir(origen):
            continue
        ext = os.path.splitext(nombre)[1].lower()
        categoria = next((c for c, extlist in _CATEGORIAS.items() if ext in extlist), "Otros")
        destino = os.path.join(carpeta, categoria)
        os.makedirs(destino, exist_ok=True)
        try:
            shutil.move(origen, os.path.join(destino, nombre))
            movidos += 1
            lineas.append(f"  {nombre} -> {categoria}/")
        except Exception as e:
            lineas.append(f"  {nombre}: error {e}")
    if not lineas:
        return "No había archivos que mover."
    return f"Organizados {movidos} archivos en {carpeta}:\n" + "\n".join(lineas)


@reg.registrar(
    "renombrar_masivo",
    descripcion="Renombra en masa los archivos de una carpeta añadiendo/quitando un texto o reemplazando texto en el nombre. Pide confirmación.",
    parametros={
        "carpeta": {"type": "string", "description": "Ruta de la carpeta.", "requerido": True},
        "buscar": {"type": "string", "description": "Texto a reemplazar en los nombres (opcional)."},
        "reemplazar": {"type": "string", "description": "Texto por el que reemplazar 'buscar' (opcional)."},
        "prefijo": {"type": "string", "description": "Prefijo a añadir a cada nombre (opcional)."},
    },
)
def renombrar(carpeta, buscar=None, reemplazar=None, prefijo=None):
    carpeta = (carpeta or "").strip().strip('"')
    if not os.path.isdir(carpeta):
        return f"Error: no existe la carpeta {carpeta}."
    if not util.pedir_confirmacion(f"¿Renombro archivos en {carpeta}?"):
        return "Cancelado: no se renombró nada."
    renombrados = 0
    lineas = []
    for nombre in os.listdir(carpeta):
        origen = os.path.join(carpeta, nombre)
        if not os.path.isfile(origen):
            continue
        nuevo = nombre
        if buscar and reemplazar is not None:
            nuevo = nuevo.replace(buscar, reemplazar)
        if prefijo:
            nuevo = prefijo + nuevo
        if nuevo == nombre or not nuevo.strip():
            continue
        destino = os.path.join(carpeta, nuevo)
        try:
            os.rename(origen, destino)
            renombrados += 1
            lineas.append(f"  {nombre} -> {nuevo}")
        except Exception as e:
            lineas.append(f"  {nombre}: error {e}")
    if not lineas:
        return "No se renombró nada (nombres sin cambios)."
    return f"Renombrados {renombrados} archivos:\n" + "\n".join(lineas)
