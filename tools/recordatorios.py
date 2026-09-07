# Tools de recordatorios: delegan en el módulo recordatorios.py ya existente.
import recordatorios
import tools.registro as reg


@reg.registrar(
    "agregar_recordatorio",
    descripcion=(
        "Programa un aviso ÚNICO (de una sola vez) con fecha u hora. NO sirve para repetir "
        "todos los días: eso es agregar_agenda_recurrente. En 'texto' pon LITERALMENTE todo "
        "lo que pidió el usuario con el momento ('avísame en 30 segundos para tomar agua', "
        "'recuérdame la reunión a las 15:30'). El sistema extrae la hora; no inventes fechas."
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
