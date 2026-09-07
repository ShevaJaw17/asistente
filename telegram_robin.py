# Bot de Telegram para Robin: chatea con el asistente desde el móvil vía
# bot.getUpdates (long polling) + sendMessage. Reutiliza el mismo pipeline que
# la GUI (memoria por contexto, herramientas, historial por chat persistido).
#
# Config en data/telegram_config.json:
#   {"token": "...", "permitidos": [], "activo": true}
# Si "permitidos" está vacío, el primer usuario que escriba queda autorizado.
import json
import os
import threading
import time

import asistente

_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CONFIG = os.path.join(_DIR, "data", "telegram_config.json")
ARCHIVO_HISTORIAL = os.path.join(_DIR, "data", "telegram_historial.json")

BASE = "https://api.telegram.org/bot{token}"
LIMITE_HISTORIAL = 40
OFFSET = 0

_hilo = None
_detener = threading.Event()
_httpx = None


def _cargar_config():
    try:
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_config(cfg):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_CONFIG), exist_ok=True)
        with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _cargar_historial():
    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_historial(h):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_HISTORIAL), exist_ok=True)
        with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _api():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx.Client(timeout=60)
    return _httpx


def _permitido(chat_id):
    cfg = _cargar_config()
    permitidos = cfg.get("permitidos") or []
    if not permitidos:
        # Auto-autorización: primer usuario autorizado y guardado.
        cfg["permitidos"] = [chat_id]
        _guardar_config(cfg)
        return True
    return chat_id in permitidos


def _responder(chat_id, texto):
    """Procesa un mensaje con el pipeline completo de Robin y devuelve la respuesta."""
    historial = _cargar_historial()
    mensajes = historial.get(str(chat_id), [])
    try:
        system_msj = asistente.sistema_con_contexto(texto)
    except Exception:
        system_msj = ""
    if not mensajes or mensajes[0].get("role") != "system":
        mensajes = [{"role": "system", "content": system_msj}] + mensajes
    if len(mensajes) > 60:
        mensajes = [mensajes[0]] + mensajes[-50:]
    mensajes.append({"role": "user", "content": texto})
    try:
        mensaje = asistente.responder_asistente(mensajes)
    except Exception as e:
        return f"Error de conexión con el asistente: {e}"
    mensajes.append({"role": "assistant", "content": mensaje.get("content", ""),
                     "tool_calls": mensaje.get("tool_calls")})
    vueltas = 0
    while mensaje.get("tool_calls") and vueltas < 6:
        for llamada in mensaje["tool_calls"]:
            nombre = llamada["function"]["name"]
            args = llamada["function"].get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            try:
                resultado = asistente.ejecutar_herramienta(nombre, args)
            except Exception as e:
                resultado = f"Error ejecutando herramienta: {e}"
            mensajes.append({"role": "tool", "tool_call_id": llamada.get("id", ""),
                             "content": str(resultado)})
        try:
            mensaje = asistente.responder_asistente(mensajes)
        except Exception as e:
            mensaje = {"content": f"Error de conexión: {e}"}
            break
        mensajes.append({"role": "assistant", "content": mensaje.get("content", "")})
        vueltas += 1
    # Conserva el historial (sin el system que se recalcula por turno).
    pub = {"role": "user", "content": texto}
    resp = {"role": "assistant", "content": mensaje.get("content", "")}
    historial.setdefault(str(chat_id), [])
    historial[str(chat_id)].extend([pub, resp])
    if len(historial[str(chat_id)]) > LIMITE_HISTORIAL:
        historial[str(chat_id)] = historial[str(chat_id)][-LIMITE_HISTORIAL:]
    _guardar_historial(historial)
    return mensaje.get("content", "")


def _enviar(chat_id, texto):
    token = _cargar_config().get("token", "")
    if not token:
        return
    ruta = f"{BASE.format(token=token)}/sendMessage"
    try:
        _api().post(ruta, json={"chat_id": chat_id, "text": texto[:4000]})
    except Exception:
        pass


def _procesar_update(update):
    mensaje = (update or {}).get("message") or {}
    texto = (mensaje.get("text") or "").strip()
    if not texto:
        return
    chat_id = mensaje.get("chat", {}).get("id")
    if chat_id is None:
        return
    if not _permitido(chat_id):
        _enviar(chat_id, "No estoy autorizado para hablar contigo.")
        return
    if texto.lower() in ("/start", "/ayuda", "/help"):
        _enviar(chat_id,
                "¡Hola! Soy tu asistente Robin. Escríbeme con normalidad:\n"
                "- 'recuerda que mi color favorito es el azul'\n"
                "- 'agrega una tarea comprar pan'\n"
                "- 'exporta mis tareas a pdf'\n"
                "- '¿cuál es mi nombre?'\n"
                "Funciono con herramientas y memoria del sistema.")
        return
    resp = _responder(chat_id, texto)
    _enviar(chat_id, resp or "No pude generar una respuesta.")


def _bucle():
    global OFFSET
    while not _detener.is_set():
        token = _cargar_config().get("token", "").strip()
        if not token:
            _detener.wait(3)
            continue
        ruta = f"{BASE.format(token=token)}/getUpdates"
        try:
            r = _api().post(ruta, json={"offset": OFFSET, "timeout": 25})
            datos = r.json()
            if not datos.get("ok"):
                _detener.wait(5)
                continue
            for upd in datos.get("result", []):
                OFFSET = max(OFFSET, int(upd.get("update_id", OFFSET)) + 1)
                threading.Thread(target=_procesar_update, args=(upd,), daemon=True).start()
        except Exception:
            _detener.wait(5)


def iniciar_bot(background=True):
    """Arranca el bot en un hilo (por defecto). Devuelve True si hay token."""
    global _hilo
    cfg = _cargar_config()
    if not cfg.get("token", "").strip():
        return False
    if _hilo is not None and _hilo.is_alive():
        return True
    _detener.clear()
    _hilo = threading.Thread(target=_bucle, daemon=True)
    _hilo.start()
    return True


def detener_bot():
    _detener.set()
    global _hilo
    _hilo = None


def estado_bot():
    cfg = _cargar_config()
    token = cfg.get("token", "")
    activo = bool(token) and _hilo is not None and _hilo.is_alive()
    return {
        "configurado": bool(token),
        "activo": activo,
        "permitidos": cfg.get("permitidos") or [],
        "token_trucado": (token[:12] + "…" if len(token) > 16 else token),
    }


if __name__ == "__main__":
    print("Bot de Telegram para Robin")
    if not iniciar_bot():
        print("Sin token configurado. Edita data/telegram_config.json (campo 'token').")
    else:
        print("Bot activo. Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            detener_bot()
            print("Bot detenido.")