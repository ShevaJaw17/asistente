# Servidor web para hablar con el asistente desde el celular u otra máquina.
#
# Uso:
#   venv\\Scripts\\python.exe servidor_web.py
# Luego abre http://<ip-de-esta-máquina>:8000 en tu celular (misma red WiFi).
#
# Endpoints:
#   GET  /               -> interfaz de chat web
#   POST /chat           -> envía un mensaje (cuerpo: {"client_id":..., "mensaje":...})
#   POST /nueva          -> reinicia la conversación de un cliente ({"client_id":...})
import json
import threading
from datetime import datetime

import asistente
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Asistente Robin - Servidor Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sesiones: client_id -> {"mensajes": [...], "lock": threading.Lock()}
SESIONES = {}
_SESIONES_LOCK = threading.Lock()

MAX_MENSAJES = 200


class ChatRequest(BaseModel):
    client_id: str = "default"
    mensaje: str


class NuevaRequest(BaseModel):
    client_id: str = "default"


def _obtener_sesion(client_id):
    with _SESIONES_LOCK:
        if client_id not in SESIONES:
            SESIONES[client_id] = {
                "mensajes": [
                    {
                        "role": "system",
                        "content": asistente.sistema_con_contexto(),
                    }
                ],
                "lock": threading.Lock(),
            }
        return SESIONES[client_id]


def _procesar(mensajes):
    """Responde a una conversación completa manejando el loop de tools
    (misma lógica que interfaz.py)."""
    while True:
        mensaje = asistente.responder_asistente(mensajes)
        mensajes.append(
            {
                "role": "assistant",
                "content": mensaje.get("content", ""),
                "tool_calls": mensaje.get("tool_calls"),
            }
        )
        tool_calls = mensaje.get("tool_calls")
        if not tool_calls:
            texto = mensaje.get("content", "")
            try:
                asistente.guardar_intercambio(mensajes)
            except Exception:
                pass
            return texto
        for llamada in tool_calls:
            nombre = llamada["function"]["name"]
            args = llamada["function"].get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            resultado = asistente.ejecutar_herramienta(nombre, args)
            mensajes.append(
                {
                    "role": "tool",
                    "tool_call_id": llamada.get("id", ""),
                    "content": str(resultado),
                }
            )


@app.post("/chat")
def chat(req: ChatRequest):
    sesion = _obtener_sesion(req.client_id)
    with sesion["lock"]:
        mensajes = sesion["mensajes"]
        if len(mensajes) > MAX_MENSAJES:
            # Recortar histórico conservando el system prompt.
            mensajes = [mensajes[0]] + mensajes[-MAX_MENSAJES:]
            sesion["mensajes"] = mensajes
        mensaje = (req.mensaje or "").strip()
        if not mensaje:
            return {"respuesta": "Dime algo."}
        try:
            mensajes.append({"role": "user", "content": mensaje})
            respuesta = _procesar(mensajes)
            return {"respuesta": respuesta}
        except Exception as e:
            return {"respuesta": f"[Error] {e}"}


@app.post("/nueva")
def nueva(req: NuevaRequest):
    with _SESIONES_LOCK:
        SESIONES.pop(req.client_id, None)
    return {"ok": True, "mensaje": "Conversación reiniciada."}


_PAGINA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robin - Asistente Web</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, sans-serif; background:#12151f; color:#e6e6e6; }
  header { background:#1d2130; padding:12px 16px; font-weight:600; border-bottom:1px solid #2c3145; }
  header small { color:#8a91a8; font-weight:400; }
  #chat { height: calc(100vh - 120px); overflow-y:auto; padding:16px; max-width:720px; margin:0 auto; }
  .msg { margin:10px 0; display:flex; }
  .msg.user { justify-content:flex-end; }
  .bubble { max-width:78%; padding:10px 14px; border-radius:14px; white-space:pre-wrap; }
  .user .bubble { background:#2f6fed; }
  .robin .bubble { background:#232837; }
  #barra { position:fixed; bottom:0; left:0; right:0; background:#1d2130; padding:10px 16px; display:flex; gap:8px; max-width:720px; margin:0 auto; }
  input { flex:1; padding:12px; border-radius:10px; border:1px solid #2c3145; background:#12151f; color:#e6e6e6; font-size:16px; }
  button { padding:12px 18px; border:none; border-radius:10px; background:#2f6fed; color:#fff; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.5; }
</style>
</head>
<body>
<header>Robin — Asistente <small>· «__FECHA__»</small></header>
<div id="chat"></div>
<div id="barra">
  <input id="inp" placeholder="Escribe aquí..." autocomplete="off">
  <button id="btn">Enviar</button>
</div>
<script>
  var clientId = 'web-' + Math.random().toString(36).slice(2, 10);
  var chat = document.getElementById('chat');
  var inp = document.getElementById('inp');
  var btn = document.getElementById('btn');
  function add(texto, quien) {
    var div = document.createElement('div');
    div.className = 'msg ' + quien;
    div.innerHTML = '<div class="bubble"></div>';
    div.querySelector('.bubble').textContent = texto;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }
  async function enviar() {
    var texto = inp.value.trim();
    if (!texto || btn.disabled) return;
    add(texto, 'user');
    inp.value = '';
    btn.disabled = true;
    try {
      var r = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({client_id: clientId, mensaje: texto})
      });
      var d = await r.json();
      add(d.respuesta || '[sin respuesta]', 'robin');
    } catch (e) {
      add('[Error de conexión: ' + e + ']', 'robin');
    }
    btn.disabled = false;
    inp.focus();
  }
  btn.onclick = enviar;
  inp.onkeydown = function(e){ if (e.key === 'Enter') enviar(); };
  add('Hola, soy Robin. ¿En qué te ayudo?', 'robin');
  inp.focus();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def inicio():
    hoy = datetime.now().strftime("%Y-%m-%d")
    return _PAGINA.replace("__FECHA__", hoy)


if __name__ == "__main__":
    import uvicorn

    print("=== Asistente Robin - Servidor Web ===")
    print("Asegúrate de que llama.cpp esté corriendo (iniciar_servidor.bat).")
    print("Abre http://<IP-de-esta-máquina>:8000 en tu celular (misma WiFi).")
    print("Local: http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
