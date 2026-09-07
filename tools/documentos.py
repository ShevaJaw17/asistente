# Creación de documentos Word (.docx) para el asistente.
# Convierte texto sencillo (títulos #, negritas **, listas -) en un .docx
# bien formateado. La salida por defecto es la carpeta Documentos del usuario.
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


def _marcar_fuente(parrafo, texto):
    """Aplica negritas/cursivas **texto** en un párrafo (inline simple)."""
    partes = re.split(r"(\*\*[^*]+\*\*)", texto)
    for parte in partes:
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            run = parrafo.add_run(parte[2:-2])
            run.bold = True
        else:
            parrafo.add_run(parte)


def _a_html(contenido):
    """Convierte el texto markdown-lite a HTML simple para reportlab."""
    contenido = (contenido or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    contenido = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", contenido)
    return contenido


def _guardar_pdf(titulo, contenido, ruta):
    """Convierte texto markdown-lite a un PDF con reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    estilo_titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold",
                                   fontSize=18, leading=22, spaceAfter=14)
    estilo_h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14,
                               leading=18, spaceBefore=10, spaceAfter=4,
                               textColor=colors.HexColor("#1a365d"))
    estilo_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12,
                               leading=15, spaceBefore=8, spaceAfter=2,
                               textColor=colors.HexColor("#2b6cb0"))
    estilo_h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11,
                               leading=14, spaceBefore=6, spaceAfter=2)
    estilo_parrafo = ParagraphStyle("parrafo", fontName="Helvetica", fontSize=10,
                                    leading=14, spaceAfter=5)
    estilo_viñeta = ParagraphStyle("viñeta", parent=estilo_parrafo, leftIndent=14,
                                   bulletIndent=4, spaceAfter=3)

    doc = SimpleDocTemplate(ruta, pagesize=A4)
    story = [Paragraph(_a_html(titulo), estilo_titulo)]
    for linea in (contenido or "").splitlines():
        linea = linea.rstrip()
        if not linea.strip():
            continue
        texto = linea.strip()
        if texto.startswith("### "):
            story.append(Paragraph(_a_html(texto[4:]), estilo_h3))
        elif texto.startswith("## "):
            story.append(Paragraph(_a_html(texto[3:]), estilo_h2))
        elif texto.startswith("# "):
            story.append(Paragraph(_a_html(texto[2:]), estilo_h1))
        elif texto.startswith("- ") or texto.startswith("* "):
            story.append(Paragraph(_a_html(texto[2:]), estilo_viñeta,
                                   bulletText="\u2022"))
        elif re.match(r"^\d+\.\s", texto):
            story.append(Paragraph(_a_html(re.sub(r"^\d+\.\s", "", texto)),
                                   estilo_viñeta, bulletText="\u2013"))
        else:
            story.append(Paragraph(_a_html(texto), estilo_parrafo))
        story.append(Spacer(1, 2))
    doc.build(story)


def _guardar_xlsx(titulo, contenido, ruta):
    """Convierte texto markdown-lite a una hoja de cálculo:
    - Líneas con ';' se vuelven filas de varias celdas.
    - Líneas 'clave: valor' se vuelven dos columnas.
    - Líneas con '#'/'-' se ignoran (solo dan estructura a la hoja)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo[:31] or "Hoja1"
    hoja["A1"] = titulo
    hoja["A1"].font = Font(bold=True, size=13)
    fila = 2
    for linea in (contenido or "").splitlines():
        linea = linea.rstrip()
        if not linea.strip():
            continue
        texto = linea.strip()
        if texto.startswith("#") or texto.startswith("- ") or texto.startswith("* "):
            continue
        if ";" in texto:
            hoja.append([c.strip() for c in texto.split(";")])
        elif ": " in texto and not texto.startswith((" ", "-")):
            c1, _, c2 = texto.partition(": ")
            hoja.append([c1.strip(), c2.strip()])
        else:
            hoja.append([texto])
        fila += 1
    # Negrita en el encabezado si la primera fila de datos parece cabecera.
    if fila > 2 and hoja.cell(row=2, column=1).value:
        primera = [c for c in hoja[2]]
        if all(c.value for c in primera):
            for c in primera:
                c.font = Font(bold=True)
    try:
        from openpyxl.utils import column_index_from_string
        hoja.column_dimensions["A"].width = 30
        for col in "BCDEFGHIJK":
            hoja.column_dimensions[col].width = 22
    except Exception:
        pass
    libro.save(ruta)


def _agregar_contenido(doc, contenido):
    """Convierte líneas de texto (markdown-lite) a párrafos de Word."""
    for linea in (contenido or "").splitlines():
        linea = linea.rstrip()
        if not linea.strip():
            continue
        texto = linea.strip()
        if texto.startswith("### "):
            doc.add_heading(texto[4:], level=3)
        elif texto.startswith("## "):
            doc.add_heading(texto[3:], level=2)
        elif texto.startswith("# "):
            doc.add_heading(texto[2:], level=1)
        elif texto.startswith("- ") or texto.startswith("* "):
            parrafo = doc.add_paragraph(style="List Bullet")
            _marcar_fuente(parrafo, texto[2:])
        elif texto.startswith("1. ") or re.match(r"^\d+\.\s", texto):
            parrafo = doc.add_paragraph(style="List Number")
            _marcar_fuente(parrafo, re.sub(r"^\d+\.\s", "", texto))
        else:
            parrafo = doc.add_paragraph()
            _marcar_fuente(parrafo, texto)


@reg.registrar(
    "crear_documento",
    descripcion=(
        "Crea un documento (Word .docx, PDF .pdf u hoja de cálculo .xlsx) con el "
        "contenido indicado y lo guarda en el disco. Úsala cuando el usuario pida "
        "'hazme un documento', 'crea un archivo de Word/PDF/hoja de cálculo', "
        "'escribe un documento sobre X', 'exporta esto a PDF' o 'hazme un "
        "documento con mis datos'. El contenido se escribe como texto (usa # para "
        "títulos, **texto** para negritas y - para listas). Para .xlsx, usa ';' "
        "para separar celdas de una fila o 'clave: valor' para dos columnas."
    ),
    parametros={
        "titulo": {"type": "string", "description": "Título del documento (aparece como encabezado).", "requerido": True},
        "contenido": {"type": "string", "description": "Cuerpo del documento en texto (títulos #, negritas **, listas -, celdas con ;).", "requerido": True},
        "formato": {"type": "string", "description": "Formato de salida: 'docx' (Word, por defecto), 'pdf' o 'xlsx' (hoja de cálculo)."},
        "carpeta": {"type": "string", "description": "Carpeta de destino (opcional; por defecto la carpeta Documentos del usuario)."},
    },
)
def crear_documento(titulo, contenido, formato="docx", carpeta=None):
    titulo = (titulo or "").strip()
    contenido = (contenido or "").strip()
    formato = (formato or "docx").strip().lower().lstrip(".")
    if formato not in ("docx", "pdf", "xlsx"):
        return "Error: formato no válido. Usa 'docx', 'pdf' o 'xlsx'."
    if not titulo or not contenido:
        return "Error: falta el título o el contenido del documento."
    destino = (carpeta or "").strip().strip('"') or _carpeta_documentos()
    if not os.path.isdir(destino):
        try:
            os.makedirs(destino, exist_ok=True)
        except Exception as e:
            return f"Error: no puedo crear la carpeta {destino}: {e}"
    nombre = re.sub(r"[\\/:*?\"<>|]", "-", titulo)
    ruta = os.path.join(destino, f"{nombre}.{formato}")
    if formato == "pdf":
        try:
            _guardar_pdf(titulo, contenido, ruta)
        except ImportError:
            return "Error: reportlab no está instalado (pip install reportlab)."
        except Exception as e:
            return f"Error al guardar el PDF: {e}"
        return f"Documento creado y guardado en:\n{ruta}\n\nTítulo: {titulo}"
    if formato == "xlsx":
        try:
            _guardar_xlsx(titulo, contenido, ruta)
        except ImportError:
            return "Error: openpyxl no está instalado (pip install openpyxl)."
        except Exception as e:
            return f"Error al guardar la hoja de cálculo: {e}"
        return f"Hoja de cálculo creada y guardada en:\n{ruta}\n\nTítulo: {titulo}"
    try:
        from docx import Document
    except ImportError:
        return "Error: python-docx no está instalado (pip install python-docx)."
    doc = Document()
    doc.add_heading(titulo, level=0)
    _agregar_contenido(doc, contenido)
    try:
        doc.save(ruta)
    except Exception as e:
        return f"Error al guardar el documento: {e}"
    return f"Documento creado y guardado en:\n{ruta}\n\nTítulo: {titulo}"


# -------------------- PLANTILLAS DE DOCUMENTOS --------------------
# Plantillas con campos {placeholder} que la tool rellena con `datos`.
PLANTILLAS = {
    "informe": (
        "# {titulo}\n"
        "**Fecha:** {fecha}  **Autor:** {autor}\n\n"
        "## Resumen\n{resumen}\n\n"
        "## Desarrollo\n{desarrollo}\n\n"
        "## Conclusiones\n{conclusiones}"
    ),
    "plan_semanal": (
        "# Plan semanal: {titulo}\n"
        "**Semana del {fecha}**\n\n"
        "- **Lunes:** {lunes}\n"
        "- **Martes:** {martes}\n"
        "- **Miércoles:** {miercoles}\n"
        "- **Jueves:** {jueves}\n"
        "- **Viernes:** {viernes}\n"
        "- **Fin de semana:** {finde}\n\n"
        "**Objetivo de la semana:** {objetivo}"
    ),
    "curriculum": (
        "# {nombre}\n"
        "**Contacto:** {contacto}  **Perfil:** {perfil}\n\n"
        "## Experiencia\n{experiencia}\n\n"
        "## Formación\n{formacion}\n\n"
        "## Habilidades\n{habilidades}"
    ),
    "lista_compra": (
        "# Lista de la compra\n"
        "**Fecha:** {fecha}\n\n"
        "- {articulos}"
    ),
    "reunion": (
        "# Reunión: {titulo}\n"
        "**Fecha:** {fecha}   **Asistentes:** {asistentes}\n\n"
        "## Temas\n{temas}\n\n"
        "## Acuerdos\n{acuerdos}\n\n"
        "## Próximos pasos\n{pasos}"
    ),
}


@reg.registrar(
    "crear_plantilla",
    descripcion=(
        "Crea un documento a partir de una plantilla predefinida. Plantillas "
        "disponibles: 'informe', 'plan_semanal', 'curriculum', 'lista_compra' y "
        "'reunion'. Pasa los datos como líneas 'campo: valor' (los campos "
        "dependen de la plantilla; ver listar_plantillas). Ej: usar_plantilla "
        "tipo: plan_semanal, titulo: Semana 12, con lunes, martes, objetivo..."
    ),
    parametros={
        "tipo": {"type": "string", "description": "Nombre de la plantilla: informe, plan_semanal, curriculum, lista_compra, reunion.", "requerido": True},
        "titulo": {"type": "string", "description": "Título / nombre del documento.", "requerido": True},
        "datos": {"type": "string", "description": "Líneas 'campo: valor' que rellenan la plantilla (deja vacíos los que no apliquen).", "requerido": True},
        "formato": {"type": "string", "description": "Formato de salida: docx (por defecto), pdf o xlsx."},
        "carpeta": {"type": "string", "description": "Carpeta de destino (por defecto Documentos)."},
    },
)
def crear_plantilla(tipo, titulo, datos, formato="docx", carpeta=None):
    tipo = (tipo or "").strip().lower()
    plantilla = PLANTILLAS.get(tipo)
    if not plantilla:
        return "Plantilla no válida. Disponibles: " + ", ".join(sorted(PLANTILLAS))
    campos = {}
    for linea in (datos or "").splitlines():
        if ":" in linea:
            cl, _, val = linea.partition(":")
            campos[cl.strip().lower()] = val.strip()
    try:
        from datetime import date
        campos.setdefault("fecha", date.today().strftime("%d/%m/%Y"))
    except Exception:
        pass
    campos.setdefault("titulo", titulo)
    contenido = plantilla
    for placeholder in re.findall(r"\{(\w+)\}", contenido):
        contenido = contenido.replace("{%s}" % placeholder,
                                      campos.get(placeholder) or "\u2014")
    return crear_documento(titulo, contenido, formato=formato, carpeta=carpeta)


@reg.registrar(
    "listar_plantillas",
    descripcion="Muestra las plantillas de documento disponibles y sus campos.",
)
def listar_plantillas():
    lineas = ["Plantillas disponibles:"]
    for nombre, plantilla in PLANTILLAS.items():
        ps = sorted(set(re.findall(r"\{(\w+)\}", plantilla)) - {"titulo"})
        lineas.append(f"- {nombre}: campos = {', '.join(ps)}")
    return "\n".join(lineas)