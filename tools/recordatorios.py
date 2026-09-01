# Tools de recordatorios: delegan en el módulo recordatorios.py ya existente.
import recordatorios
import tools.registro as reg


@reg.registrar(
    "agregar_recordatorio",
    descripcion=(
        "Programa un recordatorio con fecha y hora para avisar al usuario. En 'texto' pon "
        "LITERALMENTE todo lo que pidió el usuario, incluyendo el momento ('recuérdame tomar "
        "agua en 30 segundos', 'avísame a las 15:30 para la reunión'). El sistema extrae la "
        "hora automáticamente; no inventes fechas ni conviertas horas."
    ),
    parametros={
        "texto": {
            "type": "string",
            "description": "La petición completa del usuario, tal cual, con el momento incluido.",
            "requerido": True,
        },
        "hora": {
            "type": "string",
            "description": "Opcional. Solo úsala si es imprescindible; usa una expresión de tiempo.",
        },
    },
)
def agregar(texto, hora=None):
    return recordatorios.agregar(texto, hora)


@reg.registrar("listar_recordatorios", descripcion="Muestra todos los recordatorios programados con su estado y hora.")
def listar():
    return recordatorios.listar()


@reg.registrar(
    "borrar_recordatorio",
    descripcion="Elimina un recordatorio por el número que muestra listar_recordatorios.",
    parametros={"indice": {"type": "integer", "description": "Número del recordatorio a eliminar.", "requerido": True}},
)
def borrar(indice):
    return recordatorios.borrar(indice)
