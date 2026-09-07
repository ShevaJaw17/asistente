# Exportación de datos del asistente (tareas, notas, recuerdos, agenda...)
# a archivos .csv / .xlsx / .docx / .pdf / .txt en la carpeta Documentos.
import os
import re

import tools.asistente_util as util
import tools.registro as reg


def _carpeta_documentos():
    try:
        import ctypes.wintypes
        from ctypes import windll

        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _datos_para(que):
    """Devuelve (nombre_amigable, cabeceras, filas) para un bloque de datos."""
    que = (que or "").strip().lower()
    try:
        import tools.tareas as tareas
        import tools.notas as notas
        import tools.memoria as memoria
        import tools.memoria_semantica as ms
    except Exception:
        pass
    if que == "tareas":
        filas = tareas.cargar()
        cab = ["tarea", "completada"]
        filas = [[f.get("texto", ""), "Sí" if f.get("completada") else "No"] for f in filas]
        return "Tareas", cab, filas
    if que in ("notas", "nota"):
        cab = ["fecha", "texto"]
        filas = [[f.get("fecha", ""), f.get("texto", "")] for f in notas.cargar()]
        return "Notas", cab, filas
    if que in ("memoria", "datos"):
        cab = ["dato", "valor"]
        filas = [[k, v] for k, v in memoria.cargar_memoria().items()]
        return "Memoria", cab, filas
    if que in ("recuerdos", "recuerdos_largos", "memoria_larga", "semanticos"):
        cab = ["fecha", "recuerdo", "tipo", "prioridad"]
        filas = []
        try:
            rec = ms._cargar()
        except Exception:
            rec = []
        for f in rec:
            filas.append([f.get("fecha", ""), f.get("texto", ""),
                          f.get("etiqueta", ""), f.get("prioridad", "")])
        return "Recuerdos", cab, filas
    if que in ("recordatorios", "avisos"):
        try:
            import recordatorios
            rec = recordatorios.cargar()
        except Exception:
            rec = []
        cab = ["texto", "hora", "hecho"]
        filas = []
        for f in rec:
            filas.append([f.get("texto", ""), f.get("hora", ""),
                          "Sí" if f.get("hecho") else "No"])
        return "Recordatorios", cab, filas
    if que in ("agenda", "tareas_programadas", "programador"):
        try:
            import programador
            rec = programador.cargar()
        except Exception:
            rec = []
        cab = ["nombre", "hora", "dias", "accion", "activa"]
        filas = []
        for f in rec:
            filas.append([f.get("nombre", ""), f.get("hora", ""),
                          str(f.get("dias", "")), f.get("accion", ""),
                          "Sí" if f.get("activa") else "No"])
        return "Agenda", cab, filas
    if que == "todo":
        partes = []
        for bloque in ("tareas", "notas", "memoria", "recuerdos", "recordatorios", "agenda"):
            nombre, cab, filas = _datos_para(bloque)
            partes.append((nombre, cab, filas))
        filas_todo = []
        for nombre, cab, filas in partes:
            for fila in filas:
                filas_todo.append([nombre, " | ".join(f"{c}: {v}" for c, v in zip(cab, fila))])
        return "Resumen completo", ["bloque", "detalle"], filas_todo
    return None, [], []


def _contenido_txt(cab, filas):
    lineas = [";".join(cab)]
    for fila in filas:
        limpia = [str(c).replace(";", ",") for c in fila]
        lineas.append(";".join(limpia))
    return "\n".join(lineas)


@reg.registrar(
    "exportar_datos",
    descripcion=(
        "Exporta los datos del asistente a un archivo en la carpeta Documentos. "
        "'que' puede ser: 'tareas', 'notas', 'recuerdos', 'memoria', "
        "'recordatorios', 'agenda' o 'todo'. 'formato' puede ser 'csv', 'xlsx', "
        "'docx', 'pdf' o 'txt'. Ej: 'exporta mis tareas a pdf', 'guarda mis "
        "notas en un excel'."
    ),
    parametros={
        "que": {"type": "string", "description": "Qué datos exportar: tareas, notas, recuerdos, memoria, recordatorios, agenda o todo.", "requerido": True},
        "formato": {"type": "string", "description": "Formato: csv, xlsx, docx, pdf o txt (por defecto csv)."},
        "nombre_archivo": {"type": "string", "description": "Nombre del archivo de salida (sin extensión). Por defecto usa el nombre del bloque exportado."},
    },
)
def exportar_datos(que, formato="csv", nombre_archivo=None):
    nombre, cab, filas = _datos_para(que)
    if not nombre:
        return ("No sé qué exportar. Opciones: tareas, notas, recuerdos, "
                "memoria, recordatorios, agenda o todo.")
    formato = (formato or "csv").strip().lower().lstrip(".")
    if formato not in ("csv", "xlsx", "docx", "pdf", "txt"):
        return "Formato no válido: usa csv, xlsx, docx, pdf o txt."
    carpeta = _carpeta_documentos()
    try:
        os.makedirs(carpeta, exist_ok=True)
    except Exception as e:
        return f"Error creando la carpeta: {e}"
    base = (nombre_archivo or "").strip() or nombre
    base = re.sub(r"[\\/:*?\"<>|]", "-", base)
    ruta = os.path.join(carpeta, f"{base}.{formato}")

    if formato == "csv":
        try:
            with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
                f.write(_contenido_txt(cab, filas) + "\n")
        except Exception as e:
            return f"Error al escribir el CSV: {e}"
    elif formato == "txt":
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(f"{nombre}\n\n" + _contenido_txt(cab, filas) + "\n")
        except Exception as e:
            return f"Error al escribir el TXT: {e}"
    elif formato == "xlsx":
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
            libro = Workbook()
            hoja = libro.active
            hoja.title = nombre[:31] or "Datos"
            hoja.append(cab)
            for c in hoja[1]:
                c.font = Font(bold=True)
            for fila in filas:
                hoja.append(fila)
            for col in "ABCDEFGH":
                hoja.column_dimensions[col].width = 24
            libro.save(ruta)
        except ImportError:
            return "Error: openpyxl no está instalado (pip install openpyxl)."
        except Exception as e:
            return f"Error al guardar el Excel: {e}"
    else:  # docx / pdf → reutiliza el generador de documentos
        from tools.documentos import crear_documento
        contenido = "# " + (nombre_archivo or nombre) + "\n"
        contenido += ";".join(cab) + "\n"
        for fila in filas:
            contenido += ";".join(str(c) for c in fila) + "\n"
        return crear_documento(nombre, contenido.lstrip(), formato=formato, carpeta=carpeta)
    return f"Exportado '{nombre}' a:\n{ruta}"