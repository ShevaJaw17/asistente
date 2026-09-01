# Ejecuta una tool por su nombre (recibe kwargs validados).
import tools.registro as _r


def ejecutar(nombre, argumentos):
    """argumentos: dict de kwargs. Devuelve str con el resultado o el error."""
    definicion = _r.REGISTRO.get(nombre)
    if not definicion:
        return f"Herramienta desconocida: {nombre}"
    try:
        return definicion["funcion"](**(argumentos or {}))
    except TypeError as e:
        return f"Error en argumentos de '{nombre}': {e}"
    except Exception as e:
        return f"Error ejecutando '{nombre}': {e}"
