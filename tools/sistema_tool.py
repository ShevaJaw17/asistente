# Tools del sistema Windows: volumen, captura de pantalla, limpieza, papelera.
import sistema
import tools.asistente_util as util
import tools.registro as reg


@reg.registrar(
    "ajustar_volumen",
    descripcion="Ajusta el volumen maestro del sistema a un porcentaje (0-100). Ej: 'sube el volumen a 60'.",
    parametros={"nivel": {"type": "integer", "description": "Porcentaje de volumen a dejar (0-100).", "requerido": True}},
)
def ajustar_volumen(nivel):
    try:
        nivel = int(nivel)
    except (TypeError, ValueError):
        return "Error: 'nivel' debe ser un nÃºmero del 0 al 100."
    return sistema.ajustar_volumen(nivel)


@reg.registrar(
    "capturar_pantalla",
    descripcion="Toma una captura de pantalla completa, la guarda en 'capturas' y la abre.",
)
def capturar():
    return sistema.capturar_pantalla()


@reg.registrar(
    "limpiar_archivos_temporales",
    descripcion="Borra los archivos temporales de %TEMP% mÃ¡s antiguos de ciertos dÃ­as. Libera espacio.",
    parametros={"dias": {"type": "integer", "description": "Edad mÃ­nima en dÃ­as (por defecto 7)."}},
    requiere_confirmacion=True,
)
def limpiar_temporales(dias=7):
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        return "Error: 'dias' debe ser un nÃºmero."
    if not util.pedir_confirmacion(
        f"Â¿Puedo borrar los archivos temporales de mÃ¡s de {dias} dÃ­as? "
        "(libera espacio, no afecta a tus documentos)"
    ):
        return "Limpieza de temporales cancelada por el usuario."
    return sistema.limpiar_temporales(dias)


@reg.registrar(
    "vaciar_papelera",
    descripcion="Vacia la papelera de reciclaje del sistema por completo. Pide confirmaciÃ³n al usuario.",
    requiere_confirmacion=True,
)
def vaciar_papelera():
    if not util.pedir_confirmacion("Â¿Puedo vaciar la papelera de reciclaje?"):
        return "Vaciar papelera cancelado por el usuario."
    return sistema.vaciar_papelera()
