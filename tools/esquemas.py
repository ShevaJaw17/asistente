# Genera la lista de descripciones JSON Schema (OpenAI "tools") para llama.cpp,
# a partir del registro de plugins. También expone REGISTRO para el dispatcher.
import tools.registro as _r


def describir():
    """Convierte el registro en la lista 'tools' que espera la API del modelo."""
    herramientas = []
    for nombre, def_en in _r.REGISTRO.items():
        props = def_en.get("parametros") or {}
        required = [k for k, v in (props or {}).items() if v.get("requerido")]
        esquema = {
            "type": "object",
            "properties": {
                k: {kk: vv for kk, vv in v.items() if kk != "requerido"}
                for k, v in props.items()
            },
        }
        if required:
            esquema["required"] = required
        herramientas.append(
            {
                "type": "function",
                "function": {
                    "name": nombre,
                    "description": def_en.get("descripcion", "") or def_en.get("funcion").__doc__ or "",
                    "parameters": esquema,
                },
            }
        )
    return herramientas


REGISTRO = _r.REGISTRO
