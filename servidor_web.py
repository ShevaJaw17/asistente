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
            try:
                from tools.historial import guardar_turno

                guardar_turno(mensaje, respuesta, client_id=req.client_id)
            except Exception:
                pass
            return {"respuesta": respuesta}
        except Exception as e:
            return {"respuesta": f"[Error] {e}"}


@app.post("/nueva")
def nueva(req: NuevaRequest):
    with _SESIONES_LOCK:
        SESIONES.pop(req.client_id, None)
    return {"ok": True, "mensaje": "Conversación reiniciada."}


# ---- Panel de control remoto: agenda y tareas programadas ----
# Permite gestionar la agenda y las tareas programadas desde el móvil/web
# sin pasar por el chat. Endpoints JSON + página /panel.

@app.get("/agenda")
def agenda_listar():
    import programador
    return {"items": programador.cargar()}


@app.post("/agenda/del")
def agenda_borrar(req: ChatRequest):
    import programador
    try:
        r = programador.borrar(int(req.mensaje))
    except Exception as e:
        return {"ok": False, "mensaje": str(e)}
    return {"ok": True, "mensaje": str(r)}


@app.post("/agenda/add")
def agenda_add(req: ChatRequest):
    import json as _json
    try:
        d = _json.loads(req.mensaje)
        import programador
        r = programador.agregar(
            d.get("nombre", "Tarea"),
            d.get("hora", "00:00"),
            dias=d.get("dias", "*"),
            accion=d.get("accion", "aviso"),
            parametros=d.get("parametros"),
        )
        return {"ok": True, "mensaje": str(r)}
    except Exception as e:
        return {"ok": False, "mensaje": str(e)}


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


_PANEL = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robin - Panel de control</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, sans-serif; background:#12151f; color:#e6e6e6; }
  header { background:#1d2130; padding:12px 16px; font-weight:600; border-bottom:1px solid #2c3145; }
  main { max-width:720px; margin:0 auto; padding:16px; }
  .card { background:#1d2130; border:1px solid #2c3145; border-radius:10px; padding:12px;
          margin:12px 0; display:flex; justify-content:space-between; align-items:center; gap:10px; }
  .card .info small { color:#8a91a8; }
  input, button, select { padding:10px; border-radius:8px; border:1px solid #2c3145;
          background:#12151f; color:#e6e6e6; font-size:15px; }
  button { background:#2f6fed; color:#fff; font-weight:600; cursor:pointer; border:none; }
  button.del { background:#c0392b; }
  .fila { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
  .badge { font-size:12px; background:#2c3145; padding:2px 8px; border-radius:20px; }
  .vacio { color:#8a91a8; text-align:center; padding:20px; }
  a { color:#5b8def; }
</style>
</head>
<body>
<header>Robin — Panel de control <small>· agenda y tareas programadas</small></header>
<main>
  <h3>Nueva tarea programada</h3>
  <div class="fila">
    <input id="nombre" placeholder="Nombre/descripción">
    <input id="hora" type="time" value="09:00">
    <select id="accion">
      <option value="aviso">Aviso</option>
      <option value="comando">Comando</option>
      <option value="abrir">Abrir</option>
    </select>
  </div>
  <div class="fila">
    <select id="dias">
      <option value="*">Todos los días</option>
      <option value="0,1,2,3,4">Lunes a viernes</option>
      <option value="5,6">Fin de semana</option>
      <option value="0">Lunes</option>
      <option value="1">Martes</option>
      <option value="2">Miércoles</option>
      <option value="3">Jueves</option>
      <option value="4">Viernes</option>
      <option value="5">Sábado</option>
      <option value="6">Domingo</option>
    </select>
    <input id="param" placeholder="texto (aviso) o ruta/URL (abrir)">
    <button id="add">Añadir</button>
  </div>
  <hr>
  <h3>Agenda actual</h3>
  <div id="lista"></div>
  <p class="vacio" id="vacio" style="display:none">No hay tareas programadas.</p>
  <p><a href=".">← Ir al chat</a></p>
</main>
<script>
  var lista = document.getElementById('lista');
  var vacio = document.getElementById('vacio');
  var DIAS = ['L','M','X','J','V','S','D'];
  function cargar() {
    fetch('/agenda').then(function(r){ return r.json(); }).then(function(d){
      lista.innerHTML = '';
      if (!d.items || d.items.length === 0) { vacio.style.display='block'; return; }
      vacio.style.display = 'none';
      d.items.forEach(function(t){
        var dias = t.dias === '*' ? 'todos' : t.dias.map(function(x){return DIAS[x];}).join(',');
        var div = document.createElement('div');
        div.className = 'card';
        var info = document.createElement('div');
        info.className = 'info';
        info.innerHTML = '<strong>'+ (t.nombre||'') +'</strong> <small>'+
          t.hora + ' · ' + dias + ' · ' + (t.accion||'aviso') +
          (t.activa===false ? ' · pausada' : '') + '</small>';
        var btn = document.createElement('button');
        btn.className='del'; btn.textContent='Quitar';
        btn.onclick = function(){ fetch('/agenda/del', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({mensaje: String(t.id)})}).then(cargar); };
        div.appendChild(info); div.appendChild(btn);
        lista.appendChild(div);
      });
    });
  }
  document.getElementById('add').onclick = function(){
    var body = {
      nombre: document.getElementById('nombre').value || 'Tarea',
      hora: document.getElementById('hora').value || '09:00',
      dias: document.getElementById('dias').value,
      accion: document.getElementById('accion').value,
      parametros: { texto: document.getElementById('param').value }
    };
    fetch('/agenda/add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mensaje: JSON.stringify(body)})}).then(function(){cargar();});
  };
  cargar();
</script>
</body>
</html>"""


@app.get("/panel", response_class=HTMLResponse)
def panel():
    return _PANEL


if __name__ == "__main__":
    import uvicorn

    import programador
    programador.iniciar_hilo()

    print("=== Asistente Robin - Servidor Web ===")
    print("Asegúrate de que llama.cpp esté corriendo (iniciar_servidor.bat).")
    print("Abre http://<IP-de-esta-máquina>:8000 en tu celular (misma WiFi).")
    print("Local: http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
