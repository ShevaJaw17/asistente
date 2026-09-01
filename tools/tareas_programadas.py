# Tools de tareas programadas (cron local): acciones automáticas a ciertas horas.
import programador
import tools.registro as reg


@reg.registrar(
    "agregar_tarea_programada",
    descripcion=(
        "Programa una acción automática que se ejecutará a una hora concreta (cron local). "
        "Ej: 'programa que a las 9:00 apague la música', 'todos los días a las 18:00 avísame "
        "de hacer ejercicio'. Acciones: aviso (mensaje), comando (shell), abrir (app/URL), "
        "sistema:limpiar_temporales, sistema:vaciar_papelera, sistema:capturar_pantalla, "
        "sistema:ajustar_volumen, sistema:abrir_url."
    ),
    parametros={
        "nombre": {"type": "string", "description": "Nombre descriptivo de la tarea.", "requerido": True},
        "hora": {"type": "string", "description": "Hora en formato HH:MM (reloj 24h), ej. '09:30'.", "requerido": True},
        "dias": {
            "type": "string",
            "description": "'*' para todos los días, o lista de días separados por coma. 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo. Ej: '0,2,4'.",
        },
        "accion": {"type": "string", "description": "Tipo de acción (ver descripción). Por defecto 'aviso'."},
        "parametros": {
            "type": "object",
            "description": "Parámetros según acción. Para 'aviso': {'texto': '...'}. Para 'comando': {'comando': '...'}. Para 'abrir': {'ruta': '...'}. Para 'sistema:limpiar_temporales': {'dias': 7}. Para 'sistema:ajustar_volumen': {'nivel': 50}. Para 'sistema:abrir_url': {'url': '...'}.",
        },
    },
)
def agregar(nombre, hora, dias="*", accion="aviso", parametros=None):
    return programador.agregar(nombre, hora, dias=dias, accion=accion, parametros=parametros)


@reg.registrar(
    "listar_tareas_programadas",
    descripcion="Muestra todas las tareas programadas con su hora, días y estado (activa/pausada).",
)
def listar():
    return programador.listar()


@reg.registrar(
    "borrar_tarea_programada",
    descripcion="Elimina una tarea programada por su número (según listar_tareas_programadas).",
    parametros={"indice": {"type": "integer", "description": "Número de la tarea programada a eliminar.", "requerido": True}},
)
def borrar(indice):
    return programador.borrar(indice)


@reg.registrar(
    "pausar_tarea_programada",
    descripcion="Pausa o reanuda una tarea programada sin eliminarla.",
    parametros={
        "indice": {"type": "integer", "description": "Número de la tarea programada.", "requerido": True},
        "pausar": {"type": "boolean", "description": "True para pausar, False para reanudar.", "requerido": True},
    },
)
def pausar(indice, pausar):
    return programador.activar_desactivar(indice, not pausar)
