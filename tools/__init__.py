# Herramientas (tools) del asistente, organizadas como plugins.
#
# Cada módulo de este paquete registra en tools/registro.py:
#   @registrar("nombre", descripcion=..., parametros=..., requiere_confirmacion=...)
#   def funcion(**kwargs): return "texto resultado"
#
# "esquemas.py" convierte el registro en la lista JSON Schema que entiende el
# modelo. "dispatcher.py" ejecuta cada llamada por nombre. "asistente_util.py"
# aporta helpers compartidos (rutas a datos + confirmación).

import pkgutil

# Aseguramos que la raíz del proyecto esté en sys.path para poder importar
# utilidades_compartidas y los módulos de datos desde las tools.
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

import utilidades_compartidas  # noqa: F401  (helpers de red/portapapeles)
import tools.registro as _r  # noqa: F401  (registro compartido)

# Excluimos módulos de soporte (no son plugins con tools).
_EXCLUIDOS = {
    "registro", "esquemas", "dispatcher", "asistente_util",
    "memoria_semantica",
}


def _descubrir_modulos():
    ruta = os.path.dirname(__file__)
    for _, nombre, es_pkg in pkgutil.iter_modules([ruta]):
        if nombre in _EXCLUIDOS or es_pkg:
            continue
        try:
            __import__(f"tools.{nombre}")
        except Exception as e:  # noqa: BLE001 - un plugin no rompe el resto
            import traceback
            traceback.print_exc()
            print(f"[tools] Plugin '{nombre}' no se pudo cargar: {e}")


_descubrir_modulos()


def get_herramientas():
    """Lista JSON Schema de tools para enviar al modelo."""
    from tools import esquemas
    return esquemas.describir()


def ejecutar(nombre, argumentos):
    """Ejecuta una tool por nombre. argumentos: dict."""
    from tools import dispatcher
    return dispatcher.ejecutar(nombre, argumentos)
