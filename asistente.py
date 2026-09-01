# Asistente Virtual Local - llama.cpp (Vulkan/GPU)
# Lanzador: haz doble clic en "iniciar.bat"
import json
import os
import re
import subprocess
import urllib.parse
import webbrowser
from datetime import datetime

import httpx

import recordatorios
import sistema

SERVIDOR = "http://127.0.0.1:8080"
MODELO = "qwen2.5-7b"


def copiar_portapapeles_windows(texto):
    from utilidades_compartidas import copiar_portapapeles_windows as _f
    return _f(texto)


# Función de confirmación configurable (la GUI la sobrescribe para mostrar un diálogo)
confirmar_accion = None


def pedir_confirmacion(mensaje):
    if confirmar_accion is not None:
        return confirmar_accion(mensaje)
    try:
        respuesta = input(f"[Confirmación requerida] {mensaje} (s/n): ").strip().lower()
        return respuesta in ("s", "si", "yes", "y", "sí")
    except (EOFError, KeyboardInterrupt):
        return False
CLIENTE = httpx.Client(base_url=SERVIDOR, timeout=httpx.Timeout(300.0))

DIRECTORIO_PROYECTO = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_MEMORIA = os.path.join(DIRECTORIO_PROYECTO, "memoria.json")
ARCHIVO_TAREAS = os.path.join(DIRECTORIO_PROYECTO, "tareas.json")
ARCHIVO_NOTAS = os.path.join(DIRECTORIO_PROYECTO, "notas.json")
CLIENTE_WEB = httpx.Client(timeout=httpx.Timeout(20.0), headers={"User-Agent": "Mozilla/5.0"})


def cargar_tareas():
    if os.path.exists(ARCHIVO_TAREAS):
        try:
            with open(ARCHIVO_TAREAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_tareas(tareas):
    with open(ARCHIVO_TAREAS, "w", encoding="utf-8") as f:
        json.dump(tareas, f, ensure_ascii=False, indent=2)


def cargar_notas():
    if os.path.exists(ARCHIVO_NOTAS):
        try:
            with open(ARCHIVO_NOTAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_notas(notas):
    with open(ARCHIVO_NOTAS, "w", encoding="utf-8") as f:
        json.dump(notas, f, ensure_ascii=False, indent=2)


def cargar_memoria():
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_memoria(memoria):
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)


ARCHIVO_HISTORIAL = os.path.join(DIRECTORIO_PROYECTO, "historial.json")


def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
        except Exception:
            pass
    return []


def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def guardar_intercambio(mensajes, limite=200):
    """Guarda el último intercambio usuario -> asistente en historial.json."""
    try:
        turno = {"ts": "", "usuario": "", "asistente": ""}
        for m in mensajes[-8:]:
            if m.get("role") == "user" and not m.get("tool_calls"):
                if m.get("content"):
                    turno["usuario"] = m["content"]
            elif m.get("role") == "assistant" and not m.get("tool_calls"):
                if m.get("content"):
                    turno["asistente"] = m["content"]
        if not (turno["usuario"] or turno["asistente"]):
            return
        turno["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        historial = cargar_historial()
        historial.append(turno)
        guardar_historial(historial[-limite:])
    except Exception:
        pass


def buscar_en_internet_impl(consulta):
    from utilidades_compartidas import buscar_en_internet_impl as _f
    return _f(consulta)


def normalizar_idioma(idioma):
    from utilidades_compartidas import normalizar_idioma as _f
    return _f(idioma)


def traducir_impl(texto, origen, destino):
    from utilidades_compartidas import traducir_impl as _f
    return _f(texto, origen, destino)


def resumir_archivo_impl(ruta):
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.read()
    except FileNotFoundError:
        return f"Error: no existe el archivo {ruta}"
    except Exception as e:
        return f"Error al leer el archivo: {e}"
    if not contenido.strip():
        return "El archivo está vacío."
    contenido = contenido[:12000]
    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres un asistente que resume documentos en español. Devuelve únicamente "
                "el resumen en español: claro, breve y con un máximo de 8 frases."
            ),
        },
        {"role": "user", "content": f"Resume este texto:\n\n{contenido}"},
    ]
    try:
        data = llamar_modelo(mensajes)
        return data["choices"][0]["message"].get("content", "(sin respuesta)")
    except Exception as e:
        return f"Error al generar el resumen: {e}"


HERRAMIENTAS_DISPONIBLES = None


def _obtener_herramientas():
    """Devuelve (y cachea) la lista JSON Schema de tools del paquete tools."""
    global HERRAMIENTAS_DISPONIBLES
    if HERRAMIENTAS_DISPONIBLES is None:
        import tools
        HERRAMIENTAS_DISPONIBLES = tools.get_herramientas()
    return HERRAMIENTAS_DISPONIBLES



def ejecutar_herramienta(nombre, argumentos):
    """Ejecuta una tool delegando en el paquete tools (carga perezosa)."""
    import tools
    return tools.ejecutar(nombre, argumentos)


def llamar_modelo(mensajes, herramientas=None):
    payload = {
        "model": MODELO,
        "messages": mensajes,
        "max_tokens": 512,
        "temperature": 0.8,
    }
    if herramientas:
        payload["tools"] = herramientas
    resp = CLIENTE.post("/v1/chat/completions", json=payload)
    resp.raise_for_status()
    return resp.json()


def responder_asistente(mensajes):
    data = llamar_modelo(mensajes, _obtener_herramientas())
    return data["choices"][0]["message"]


PROMPT_SISTEMA = (
    "Eres Nico Robin, una asistente personal virtual mujer, erudita, elegante y "
    "sarcástica de forma sutil. Tienes una personalidad cálida, culta e inteligente, "
    "con un toque de humor seco y un aire tranquilo y seguro. Hablas en español de forma "
    "natural y cercana, como un amigo informado, no como un robot.\n\n"
    "Modo de hablar:\n"
    "- Usa un tono amigable y humano; tutea al usuario y muestra interés genuino.\n"
    "- Responde con naturalidad: frases conversacionales, no listas perfectas ni "
    "respuestas robóticas.\n"
    "- Cuando no sepas algo o no tengas acceso a la información, dilo con honestidad "
    "y un toque de humor, en lugar de inventar nunca.\n"
    "- Haz preguntas de vuelta cuando tenga sentido, para mantener la conversación viva.\n"
    "- No abrumes con datos: usa lo justo y con claridad, como haría una persona.\n\n"
    "REGLAS OBLIGATORIAS sobre información real y herramientas:\n"
    "1. NUNCA inventes datos que no conoces. Si el usuario pregunta por la hora, la fecha, "
    "información de archivos, del sistema, de internet, tu memoria o cualquier dato externo, "
    "SIEMPRE debes usar la herramienta correspondiente para obtenerlo.\n"
    "2. Si una herramienta falla o no está disponible, dilo con honestidad; no adivines ni fabriques.\n"
    "3. Cuando uses una herramienta, integra el resultado en tu respuesta con total naturalidad, "
    "sin mencionar que usaste una herramienta, una API o que 'consultaste tu base de datos'. "
    "Simplemente di la información como si la supieras.\n"
    "MEMORIA A LARGO PLAZO:\n"
    "5. Tienes memoria a largo plazo ('recordar_a_largo_plazo', 'recuperar_recuerdos' y "
    "'listar_recuerdos'). Cuando el usuario mencione un dato importante, una preferencia o un "
    "hecho que quiera que recuerdes para el futuro, usa 'recordar_a_largo_plazo' para guardarlo.\n"
    "6. Cuando el usuario pregunte sobre algo que pudiste haberle oído decir antes (gustos, "
    "preferencias, datos, temas hablados), usa 'recuperar_recuerdos' con las palabras clave antes "
    "de responder, en vez de adivinar.\n"
    "7. No agregues estos puntos de instrucción en tus respuestas; son solo guías internas."
)


def resumen_contexto(historial, max_caracteres=1100):
    """Devuelve fragmento de la charla anterior como contexto, sin repetir el último turno."""
    fragmentos = []
    for t in historial:
        if t.get("usuario"):
            fragmentos.append(f"Usuario: {t['usuario']}")
        if t.get("asistente"):
            fragmentos.append(f"Robin: {t['asistente']}")
    texto = "\n".join(fragmentos)
    if len(texto) > max_caracteres:
        texto = texto[-max_caracteres:]
    return texto


def sistema_con_contexto():
    """PROMPT_SISTEMA + memoria explícita + fragmento de nuestra última conversación."""
    partes = [PROMPT_SISTEMA]
    memoria = cargar_memoria()
    if memoria:
        lineas = "\n".join(f"- {c}: {v}" for c, v in memoria.items())
        partes.append(
            "MEMORIA EXPLÍCITA DEL USUARIO (usa estos datos cuando sean relevantes, "
            "no los repitas sin motivo):\n" + lineas
        )
    historial = cargar_historial()
    ultimos = historial[-8:]
    if ultimos:
        contexto = resumen_contexto(ultimos)
        if contexto:
            partes.append(
                "CONTEXTO DE NUESTRA ÚLTIMA CONVERSACIÓN (útil para continuar con "
                "naturalidad; NO lo repitas literalmente ni saludes de nuevo):\n" + contexto
            )
    return "\n\n---\n\n".join(partes)


def main():
    import programador
    programador.iniciar_hilo()
    print("=== Asistente local (qwen2.5-7b / Vulkan-GPU) ===")
    print("Servidor: " + SERVIDOR)
    print("Escribe 'salir' para terminar.")
    print()
    mensajes = [
        {
            "role": "system",
            "content": sistema_con_contexto(),
        }
    ]
    while True:
        try:
            entrada = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Adios.")
            break
        if entrada.lower() in ("salir", "exit", "quit"):
            print("Adios.")
            break
        if not entrada:
            continue
        mensajes.append({"role": "user", "content": entrada})
        try:
            mensaje = responder_asistente(mensajes)
        except Exception as e:
            print(f"\n[Error de conexión con el servidor: {e}]")
            print("Asegúrate de que el servidor llama.cpp esté corriendo (iniciar_servidor.bat).")
            mensajes.pop()
            continue
        mensajes.append({"role": "assistant", "content": mensaje.get("content", ""),
                         "tool_calls": mensaje.get("tool_calls")})
        print()
        if mensaje.get("tool_calls"):
            for llamada in mensaje["tool_calls"]:
                nombre = llamada["function"]["name"]
                args = llamada["function"].get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                print(f"[Ejecutando herramienta: {nombre} {args}]")
                resultado = ejecutar_herramienta(nombre, args)
                mensajes.append(
                    {
                        "role": "tool",
                        "tool_call_id": llamada.get("id", ""),
                        "content": str(resultado),
                    }
                )
            try:
                mensaje = responder_asistente(mensajes)
            except Exception as e:
                print(f"\n[Error: {e}]")
                mensajes.append({"role": "assistant", "content": ""})
                continue
            mensajes.append({"role": "assistant", "content": mensaje.get("content", "")})
        print(f"Asistente: {mensaje.get('content', '')}")
        print()


def main_voz():
    """Loop del asistente en modo voz (manos libres): escucha por micrófono
    y responde en voz alta. Requiere micrófono + voz.py (edge-tts / STT)."""
    import voz

    if voz is None or getattr(voz, "hablar", None) is None:
        print("La voz no está disponible. Se cae al modo texto.")
        return main()

    import programador
    programador.iniciar_hilo()

    print("=== Asistente por voz (qwen2.5-7b) ===")
    print("Escuchando... Habla y espera mi respuesta.")
    print("Di 'salir' o 'termina' para terminar.")
    print()
    mensajes = [
        {
            "role": "system",
            "content": sistema_con_contexto(),
        }
    ]
    while True:
        texto, error = voz.escuchar()
        if error:
            if error == "silencioso":
                continue  # nada que oír, seguimos escuchando
            print(f"  (no pude oírte: {error})")
            continue
        entrada = texto.strip()
        if not entrada:
            continue
        print(f"  Tú: {entrada}")
        if entrada.lower() in ("salir", "exit", "quit", "termina", "detente", "adiós"):
            print("Adiós.")
            break
        mensajes.append({"role": "user", "content": entrada})
        try:
            mensaje = responder_asistente(mensajes)
        except Exception as e:
            mensaje_error = f"No pude conectar con el servidor: {e}"
            print(f"\n[Error] {mensaje_error}")
            voz.hablar("No pude conectar con el servidor.")
            mensajes.pop()
            continue
        mensajes.append(
            {
                "role": "assistant",
                "content": mensaje.get("content", ""),
                "tool_calls": mensaje.get("tool_calls"),
            }
        )
        if mensaje.get("tool_calls"):
            for llamada in mensaje["tool_calls"]:
                nombre = llamada["function"]["name"]
                args = llamada["function"].get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                print(f"    [Herramienta: {nombre}]")
                resultado = ejecutar_herramienta(nombre, args)
                mensajes.append(
                    {
                        "role": "tool",
                        "tool_call_id": llamada.get("id", ""),
                        "content": str(resultado),
                    }
                )
            try:
                mensaje = responder_asistente(mensajes)
            except Exception as e:
                print(f"\n[Error: {e}]")
                mensajes.append({"role": "assistant", "content": ""})
                continue
            mensajes.append({"role": "assistant", "content": mensaje.get("content", "")})
        respuesta = mensaje.get("content", "")
        print(f"  Robin: {respuesta}")
        voz.hablar(respuesta)


if __name__ == "__main__":
    import sys

    if "--voz" in sys.argv or "-v" in sys.argv:
        main_voz()
    else:
        main()
