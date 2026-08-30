# avatar.py - Integración del asistente con VTube Studio (Live2D/VTuber)
# Se conecta al WebSocket de VTube Studio (ws://127.0.0.1:8001) y controla
# los parámetros del modelo para animar la boca y las expresiones.
import json
import os
import queue
import threading
import time

try:
    import websocket
except Exception:
    websocket = None

DIRECTORIO_PROYECTO = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CONFIG = os.path.join(DIRECTORIO_PROYECTO, "config_vtube.json")

CONFIG_POR_DEFECTO = {
    "host": "127.0.0.1",
    "puerto": 8001,
    "token": "",
    "activar_al_iniciar": True,
    "expresiones": {
        "pensando": "Impressed",
        "error": "Sad",
        "respuesta": "Happy",
    },
}

NOMBRE_PLUGIN = "Nico Robin Local"
DESARROLLADOR = "Asistente Local"


def cargar_config():
    cfg = dict(CONFIG_POR_DEFECTO)
    if os.path.exists(ARCHIVO_CONFIG):
        try:
            with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                datos = json.load(f)
            for clave in cfg:
                if clave in datos:
                    cfg[clave] = datos[clave]
            if isinstance(cfg.get("expresiones"), dict):
                cfg["expresiones"].update(
                    {k: v for k, v in datos.get("expresiones", {}).items()}
                )
        except Exception:
            pass
    return cfg


def guardar_config(cfg):
    try:
        with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class AvatarVTubeStudio:
    def __init__(self, on_estado=None, host=None, puerto=None):
        self.cfg = cargar_config()
        self.host = host or self.cfg.get("host") or "127.0.0.1"
        self.puerto = int(puerto or self.cfg.get("puerto") or 8001)
        self.on_estado = on_estado

        self.ws = None
        self.activo = False
        self._cerrar = False
        self._lock = threading.Lock()
        self._ids = 0
        self._cola = queue.Queue()
        self._hilo_cnx = None
        self._hilo_escucha = None
        self._hilo_boca = None

    @property
    def conectado(self):
        return self.activo and self.ws is not None

    # ----- utilidades internas -----
    def _estado(self, texto):
        if self.on_estado:
            try:
                self.on_estado(texto)
            except Exception:
                pass

    def _enviar(self, tipo, datos, esperar=True, timeout=6.0):
        if self.ws is None or not self.activo:
            return None
        self._ids += 1
        rid = str(self._ids)
        payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": rid,
            "messageType": tipo,
            "data": datos,
        }
        try:
            with self._lock:
                self.ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            self._estado(f"Avatar: error enviando {tipo}: {e}")
            return None
        if not esperar:
            return None
        fin = time.time() + timeout
        while time.time() < fin:
            try:
                msg = self._cola.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("requestID") == rid:
                return msg
        return None

    def _escuchar(self, ws):
        while not self._cerrar:
            try:
                data = ws.recv()
            except Exception:
                break
            try:
                msg = json.loads(data)
            except Exception:
                continue
            self._cola.put(msg)

    # ----- conexión / auth -----
    def conectar(self, reintentos=3):
        if websocket is None:
            self._estado("Avatar: falta el paquete websocket-client")
            return
        if self._hilo_cnx and self._hilo_cnx.is_alive():
            return
        self._cerrar = False
        while not self._cola.empty():
            try:
                self._cola.get_nowait()
            except queue.Empty:
                break
        self._hilo_cnx = threading.Thread(
            target=self._bucle_conexion, args=(reintentos,), daemon=True
        )
        self._hilo_cnx.start()

    def _bucle_conexion(self, reintentos):
        self._estado(f"Avatar: conectando a ws://{self.host}:{self.puerto}...")
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        for intento in range(1, reintentos + 1):
            if self._cerrar:
                return
            try:
                self.ws = websocket.create_connection(
                    f"ws://{self.host}:{self.puerto}", timeout=4
                )
            except Exception as e:
                if intento < reintentos:
                    self._estado(f"Avatar: sin VTube Studio, reintento {intento}/{reintentos}")
                    time.sleep(6)
                    continue
                self._estado("Avatar: VTube Studio no disponible")
                self.ws = None
                return
            break
        if self.ws is None:
            return
        self.activo = True
        self._hilo_escucha = threading.Thread(target=self._escuchar, args=(self.ws,), daemon=True)
        self._hilo_escucha.start()
        self._autenticar()

    def _autenticar(self):
        token = self.cfg.get("token") or ""
        if not token:
            self._estado("Avatar: autorización pendiente, acepta el aviso en VTube Studio...")
            resp = self._enviar(
                "AuthenticationTokenRequest",
                {"pluginName": NOMBRE_PLUGIN, "pluginDeveloper": DESARROLLADOR},
                esperar=True,
                timeout=30.0,
            )
            if not resp:
                self._estado("Avatar: no se obtuvo autorización")
                self.desconectar()
                return
            token = (resp.get("data") or {}).get("authenticationToken") or ""
            if not token:
                self._estado("Avatar: token vacío al autorizar")
                self.desconectar()
                return
            self.cfg["token"] = token
            guardar_config(self.cfg)
        resp = self._enviar(
            "AuthenticationRequest",
            {
                "pluginName": NOMBRE_PLUGIN,
                "pluginDeveloper": DESARROLLADOR,
                "authenticationToken": token,
            },
            esperar=True,
        )
        autenticado = bool((resp or {}).get("data", {}).get("authenticated"))
        if autenticado:
            self._estado("Avatar: conectado")
        else:
            motivo = (resp or {}).get("data", {}).get("reason", "desconocido")
            self._estado(f"Avatar: no autenticado ({motivo})")
            self.desconectar()

    def desconectar(self):
        self._cerrar = True
        self.activo = False
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None
        self._estado("Avatar: desconectado")

    def reconectar(self):
        self.conectar(reintentos=1)

    # ----- control del modelo -----
    def set_parametro(self, nombre, valor):
        if not self.activo:
            return
        self._enviar(
            "ParameterValueRequest",
            {"values": [{"id": nombre, "value": float(valor)}], "parameterFilter": [], "setValues": []},
            esperar=False,
        )

    def boca(self, abierta):
        self.set_parametro("MouthOpen", 1.0 if abierta else 0.0)

    def expresion(self, nombre, activa=True):
        if not self.activo:
            return
        self._enviar(
            "ExpressionRequest",
            {"expression": str(nombre), "active": bool(activa)},
            esperar=False,
        )

    def expresion_estado(self, estado):
        if not self.activo:
            return
        self.expresion(self.cfg.get("expresiones", {}).get(estado, "Neutral"))

    def hablar_texto(self, texto):
        if not self.activo or not texto:
            return
        duracion = max(0.8, min(4.0, len(texto) / 16))
        if self._hilo_boca and self._hilo_boca.is_alive():
            return
        self._hilo_boca = threading.Thread(
            target=self._animar_boca, args=(duracion,), daemon=True
        )
        self._hilo_boca.start()

    def _animar_boca(self, duracion):
        fin = time.time() + duracion
        abierta = True
        while time.time() < fin and self.activo:
            self.boca(abierta)
            abierta = not abierta
            time.sleep(0.13)
        self.boca(False)


if __name__ == "__main__":
    logging = lambda t: print(t)
    av = AvatarVTubeStudio(on_estado=logging)
    av.conectar(reintentos=2)
    time.sleep(8)
    print("Conectado u operativo:", av.activo)
    av.desconectar()