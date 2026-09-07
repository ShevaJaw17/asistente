# Memoria a largo plazo expuesta como tools al modelo.
import tools.memoria_semantica as ms
import tools.registro as reg


@reg.registrar(
    "recordar_a_largo_plazo",
    descripcion=(
        "Guarda un hecho, dato o frase para recordarlo a largo plazo, más allá del "
        "contexto inmediato. Úsala SIEMPRE que el usuario diga 'recuerda que...', "
        "'no olvides que...', 'guarda esto', 'apunta este dato', o dé información personal "
        "permanente (cumpleaños, preferencias, gustos, contactos, decisiones). "
        "Ej: 'recuerda que mi cumpleaños es el 15 de mayo'. Devuelve lo guardado."
    ),
    parametros={
        "frase": {"type": "string", "description": "El hecho o dato a recordar, en forma de frase completa.", "requerido": True},
        "etiqueta": {"type": "string", "description": "Etiqueta corta opcional para agrupar (ej. 'nombre', 'gusto')."},
        "prioridad": {"type": "string", "description": "Opcional: 'alta', 'media' o 'baja'. Por defecto alta si es dato personal o de contacto, media en otro caso.", "enum": ["alta", "media", "baja"]},
    },
)
def recordar(frase, etiqueta=None, prioridad=None):
    return ms.recordar(frase, etiqueta, prioridad)


@reg.registrar(
    "recuperar_recuerdos",
    descripcion=(
        "Busca en la memoria a largo plazo hechos o datos relacionados con la consulta "
        "del usuario. Úsalo cuando pregunte algo que dependa de información que pudo "
        "decir antes ('¿qué me gusta?', '¿cuál es mi autógrafo favorito?', 'de qué hablamos')."
    ),
    parametros={"consulta": {"type": "string", "description": "Tema o palabras clave a buscar en la memoria.", "requerido": True}},
)
def recuperar(consulta):
    resultado = ms.buscar(consulta)
    if not resultado:
        return "No encontré recuerdos relacionados con esa consulta en mi memoria a largo plazo."
    return resultado


@reg.registrar(
    "listar_recuerdos",
    descripcion=(
        "Muestra TODO lo guardado en la memoria a largo plazo, sin filtrar por tema. "
        "Úsala cuando pida 'muéstrame mis recuerdos', 'qué recuerdas de mí', 'qué tengo "
        "guardado'. NO es una búsqueda: no lleva consulta."
    ),
)
def listar():
    return ms.recuerdos()


@reg.registrar(
    "editar_recuerdo",
    descripcion=(
        "Modifica el texto de un recuerdo guardado a largo plazo. Especifica qué recuerdo "
        "editar ('referencia': puede ser el número que muestra listar_recuerdos o parte del "
        "texto) y el 'nuevo_texto' con el contenido corregido."
    ),
    parametros={
        "referencia": {"type": "string", "description": "Número del recuerdo (según listar_recuerdos) o texto que lo identifica.", "requerido": True},
        "nuevo_texto": {"type": "string", "description": "El texto nuevo que sustituirá al recuerdo.", "requerido": True},
    },
)
def editar(referencia, nuevo_texto):
    return ms.editar(referencia, nuevo_texto)


@reg.registrar(
    "olvidar_recuerdo",
    descripcion=(
        "Borra un recuerdo de la memoria a largo plazo. Especifica qué recuerdo olvidar "
        "('referencia': número de listar_recuerdos o una parte del texto, ej. 'cumpleaños')."
    ),
    parametros={"referencia": {"type": "string", "description": "Número del recuerdo (según listar_recuerdos) o texto que lo identifica.", "requerido": True}},
)
def olvidar(referencia):
    return ms.olvidar(referencia)
