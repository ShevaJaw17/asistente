# Tools para el bot de Telegram: configurar token, autorizar usuarios e
# iniciar/detener el bot desde el chat de Robin.
import os

import tools.asistente_util as util
import tools.registro as reg

_DIR_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ARCHIVO_CONFIG = os.path.join(_DIR_RAIZ, "data", "telegram_config.json")


def _leer_cfg():
    import json
    try:
        with open(_ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@reg.registrar(
    "configurar_telegram",
    descripcion=(
        "Configura el bot de Telegram con el token de BotFather y arranca el "
        "bot si hay token. Opcionalmente puedes limitar quién puede escribirle. "
        "Ej: 'configura mi bot de telegram con el token 123456:ABC...'."
    ),
    parametros={
        "token": {"type": "string", "description": "Token del bot que te da BotFather (@BotFather en Telegram).", "requerido": True},
        "permitidos": {"type": "string", "description": "User IDs permitidos (separados por coma). Vacío = el primer usuario que escriba queda autorizado."},
    },
)
def configurar_telegram(token, permitidos=None):
    token = (token or "").strip()
    if len(token) < 20:
        return ("El token parece incompleto. Debe ser el que te da @BotFather "
                "con formato 123456789:AA... (cópialo entero).")
    import json as _json
    cfg = _leer_cfg()
    cfg["token"] = token
    if permitidos:
        ids = []
        for p in str(permitidos).replace(",", " ").split():
            if p.strip().lstrip("-").isdigit():
                ids.append(int(p.strip()))
        if ids:
            cfg["permitidos"] = ids
    try:
        os.makedirs(os.path.dirname(_ARCHIVO_CONFIG), exist_ok=True)
        with open(_ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"No se pudo guardar la configuración: {e}"
    try:
        import telegram_robin as tg
        if tg.iniciar_bot():
            return ("Bot de Telegram configurado y activo.\n"
                    "Búscalo en Telegram por su @usuario (te lo da BotFather) "
                    "y escríbele para probarlo.")
        return ("Bot de Telegram configurado, pero aún no está en línea. "
                "Revisa que el token sea válido.")
    except Exception as e:
        return f"Configuración guardada, pero no se pudo arrancar el bot: {e}"


@reg.registrar(
    "estado_telegram",
    descripcion="Muestra el estado del bot de Telegram: si está configurado, en línea y con quién puede hablar.",
)
def estado_telegram():
    try:
        import telegram_robin as tg
        est = tg.estado_bot()
    except Exception:
        return "No se pudo comprobar el estado del bot de Telegram."
    lineas = ["Bot de Telegram:"]
    lineas.append(f"- Configurado: {'sí' if est['configurado'] else 'no'} "
                  f"(token {est['token_trucado'] if est['configurado'] else ''})")
    lineas.append(f"- En línea: {'sí' if est['activo'] else 'no'}")
    permitidos = est.get("permitidos") or []
    lineas.append(f"- Usuarios autorizados: {', '.join(map(str, permitidos)) if permitidos else 'cualquiera (auto-autoriza al primero)'}")
    if not est["configurado"]:
        lineas.append("Para activarlo: 'configura mi telegram con el token <TOKEN> de BotFather'.")
    return "\n".join(lineas)


@reg.registrar(
    "iniciar_telegram",
    descripcion="Arranca el bot de Telegram si ya está configurado con token.",
)
def iniciar_telegram():
    try:
        import telegram_robin as tg
        if tg.iniciar_bot():
            return "Bot de Telegram en línea. Ya puedes escribirle desde la app."
        return "No hay token configurado. Usa 'configurar_telegram' con el token de BotFather."
    except Exception as e:
        return f"No se pudo iniciar el bot: {e}"


@reg.registrar(
    "detener_telegram",
    descripcion="Detiene el bot de Telegram (deja de responder en el móvil).",
)
def detener_telegram():
    try:
        import telegram_robin as tg
        tg.detener_bot()
        return "Bot de Telegram detenido."
    except Exception as e:
        return f"No se pudo detener el bot: {e}"


@reg.registrar(
    "quitar_acceso_telegram",
    descripcion="Revoca el acceso de un usuario al bot de Telegram por su ID.",
    parametros={"usuario_id": {"type": "integer", "description": "ID de usuario a revocar.", "requerido": True}},
)
def quitar_acceso_telegram(usuario_id):
    import json as _json
    cfg = _leer_cfg()
    antes = cfg.get("permitidos") or []
    despues = [p for p in antes if p != usuario_id]
    if len(despues) == len(antes):
        return f"El usuario {usuario_id} no estaba autorizado."
    cfg["permitidos"] = despues
    try:
        with open(_ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"No se pudo guardar: {e}"
    return f"Acceso revocado al usuario {usuario_id}."