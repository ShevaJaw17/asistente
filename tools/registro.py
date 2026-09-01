# Registro central de tools: los plugins añaden aquí su definición.
REGISTRO = {}


def registrar(nombre, **definicion):
    """Decorador: registra una tool en el registro global."""
    def decorador(funcion):
        REGISTRO[nombre] = {**definicion, "funcion": funcion}
        return funcion
    return decorador
