# Memoria a largo plazo expuesta como tools al modelo.
import tools.memoria_semantica as ms
import tools.registro as reg


@reg.registrar(
    "recordar_a_largo_plazo",
    descripcion=(
        "Guarda un hecho, dato o frase para recordarlo a largo plazo, más allá del "
        "contexto inmediato. Úsalo cuando el usuario pida que recuerdes algo importante "
        "o cuando menciones información que quieras tener disponible en futuras charlas "
        "(preferencias, gustos, datos personales, decisiones). Devuelve lo guardado."
    ),
    parametros={
        "frase": {"type": "string", "description": "El hecho o dato a recordar, en forma de frase completa.", "requerido": True},
        "etiqueta": {"type": "string", "description": "Etiqueta corta opcional para agrupar (ej. 'nombre', 'gusto')."},
    },
)
def recordar(frase, etiqueta=None):
    return ms.recordar(frase, etiqueta)


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
    descripcion="Muestra todo lo guardado en la memoria a largo plazo.",
)
def listar():
    return ms.recuerdos()
