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

import personalidad
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
        try:
            consolidar_memoria(mensajes)
        except Exception:
            pass
    except Exception:
        pass


# Cadencia entre consolidaciones de memoria (segundos) y última ejecución.
INTERVALO_CONSOLIDACION = 300.0  # 5 minutos
_ultima_consolidacion = 0.0


def consolidar_memoria(mensajes, forzar=False):
    """Extrae hechos nuevos de la conversación y los fusiona en la memoria.

    Se llama con moderación (ver INTERVALO_CONSOLIDACION) porque usa una llamada
    extra al modelo. Compara con lo ya guardado para evitar duplicados."""
    global _ultima_consolidacion
    ahora = datetime.now().timestamp()
    if not forzar and (ahora - _ultima_consolidacion) < INTERVALO_CONSOLIDACION:
        return None
    _ultima_consolidacion = ahora
    # Tomamos los últimos turnos texto (usuario/asistente) de la sesión actual.
    texto = ""
    for m in mensajes[-14:]:
        if m.get("role") in ("user", "assistant") and not m.get("tool_calls"):
            rol = "Usuario" if m["role"] == "user" else "Robin"
            if m.get("content"):
                texto += f"{rol}: {m['content']}\n"
    if len(texto) < 40:
        return None
    sys_extraer = (
        "Eres un extractor de datos personales. Lee la conversación y devuelve SOLO JSON "
        "válido con dos listas:\n"
        '{"hechos": [{"texto": "frase completa", "etiqueta": "gusto|dato|preferencia|otro"}], '
        '"preferencias": [{"clave": "clave_corta", "valor": "valor"}]}\n'
        "Incluye SOLO información real dicha por el usuario (nombre, cumpleaños, gustos, "
        "preferencias, datos). Omite saludos, tareas puntuales y conversación general. "
        "Si no hay nada que guardar devuelve {\"hechos\": [], \"preferencias\": []}.\n"
        "Máximo 5 hechos y 4 preferencias. No inventes nada."
    )
    try:
        data = llamar_modelo(
            [
                {"role": "system", "content": sys_extraer},
                {"role": "user", "content": texto},
            ],
            herramientas=None,
        )
        contenido = data["choices"][0]["message"].get("content", "").strip()
    except Exception as e:
        return f"(consolidación no disponible: {e})"
    try:
        extraido = json.loads(contenido)
    except Exception:
        # Intentar recuperar JSON si el modelo lo envolvió en markdown.
        inicio = contenido.find("{")
        fin = contenido.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            try:
                extraido = json.loads(contenido[inicio:fin])
            except Exception:
                return "(consolidación: JSON inválido)"
        else:
            return "(consolidación: JSON inválido)"
    resultados = []
    import tools
    for h in extraido.get("hechos", []):
        texto_h = (h.get("texto") or "").strip()
        if not texto_h:
            continue
        if _recuerdo_similar_existe(texto_h):
            continue
        resultados.append(tools.ejecutar("recordar_a_largo_plazo", {
            "frase": texto_h, "etiqueta": h.get("etiqueta") or None}))
    for p in extraido.get("preferencias", []):
        clave = (p.get("clave") or "").strip()
        valor = (p.get("valor") or "").strip()
        if clave and valor:
            resultados.append(tools.ejecutar("recordar", {"clave": clave, "valor": valor}))
    return "\n".join(resultados) if resultados else "(no había hechos nuevos que guardar)"


def _memoria_relevante(memoria, consulta, limite=4):
    """Devuelve las claves de memoria explícita más relevantes a la consulta."""
    try:
        import tools.memoria_semantica as ms
    except Exception:
        return "\n".join(f"- {c}: {v}" for c, v in memoria.items())
    consulta = (consulta or "").strip()
    items = [f"{c}: {v} {v}" for c, v in memoria.items()]
    datos = [{"texto": t} for t in items]
    df = ms._df(datos)
    n = len(datos)
    vq = ms._vector_consulta(consulta, df, n)
    pares = []
    for clave, valor in memoria.items():
        vh = ms._vector_consulta(f"{clave}: {valor}", df, n)
        pares.append((ms._similitud(vq, vh), clave, valor))
    pares.sort(reverse=True)
    seleccion = [(c, v) for s, c, v in pares if s > 0.05][:limite]
    if not seleccion:
        pares2 = sorted(memoria.items())
        seleccion = pares2[:2]
    return "\n".join(f"- {c}: {v}" for c, v in seleccion)


def _memoria_semantica_relevante(consulta, limite=3):
    """Recuerdos a largo plazo relevantes a la consulta (para inyectar en el prompt)."""
    try:
        import tools.memoria_semantica as ms
        return ms.buscar(consulta, limite=limite, umbral=0.08)
    except Exception:
        return ""


def _recuerdo_similar_existe(frase, umbral=0.55):
    """Coincide aproximadamente (semántica ligera) con un recuerdo ya guardado."""
    try:
        import tools.memoria_semantica as ms
        datos = ms._cargar()
        if not datos:
            return False
        df = ms._df(datos)
        vq = ms._vector_consulta(frase, df, len(datos))
        for hecho in datos:
            vh = ms._vector_consulta(hecho.get("texto", ""), df, len(datos))
            if ms._similitud(vq, vh) >= umbral:
                return True
        return False
    except Exception:
        return False


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
        "temperature": 0.4,
    }
    if herramientas:
        payload["tools"] = herramientas
    resp = CLIENTE.post("/v1/chat/completions", json=payload)
    resp.raise_for_status()
    return resp.json()


def responder_asistente(mensajes):
    data = llamar_modelo(mensajes, _obtener_herramientas())
    return data["choices"][0]["message"]


# ---- Streaming (TTS en paralelo con el texto) ----
# El texto se devuelve por fragmentos ("frases") apenas el modelo los genera,
# para que la voz pueda empezar a hablar antes de que termine toda la respuesta.
_CORTE_FRASE = ".\n¿?¡!;"


def _llamar_modelo_stream(mensajes, herramientas=None, on_token=None):
    """Llama al modelo en streaming.
    - Acumula el texto completo y las tool_calls.
    - Si `on_token` se pasa, se invoca on_token(texto_parcial) con cada trozo de
      texto en tiempo real (para poder fragmentar por frases apenas llegan).
    Devuelve (texto, tool_calls, finish_reason)."""
    payload = {
        "model": MODELO,
        "messages": mensajes,
        "max_tokens": 512,
        "temperature": 0.4,
        "stream": True,
    }
    if herramientas:
        payload["tools"] = herramientas
    texto = ""
    tool_calls = {}
    orden = []
    with CLIENTE.stream("POST", "/v1/chat/completions", json=payload) as resp:
        resp.raise_for_status()
        for linea in resp.iter_lines():
            if not linea or not linea.startswith("data:"):
                continue
            d = linea[5:].strip()
            if not d:
                continue
            try:
                obj = _json_stream(d)
            except Exception:
                continue
            ch = (obj.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if delta.get("content"):
                trozo = delta["content"]
                texto += trozo
                if on_token:
                    try:
                        on_token(trozo)
                    except Exception:
                        pass
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                if idx not in tool_calls:
                    tool_calls[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                    orden.append(idx)
                fn = tc.get("function") or {}
                if tc.get("id"):
                    tool_calls[idx]["id"] = tc["id"]
                if fn.get("name"):
                    tool_calls[idx]["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    tool_calls[idx]["function"]["arguments"] += fn["arguments"]
    return texto, [tool_calls[i] for i in orden]


def _json_stream(s):
    import json as _json
    return _json.loads(s)


def responder_streaming(mensajes, on_fragmento=None):
    """Mismo chat que responder_asistente pero en modo streaming: invoca
    `on_fragmento(texto)` por cada frase del texto final apenas se genera.
    Devuelve el texto completo. Maneja las tools igual que el chat normal."""
    acumulador = [""]
    # Buffer para fragmentar frases en vivo
    buf = [""]

    def _emitir_en_vivo(trozo):
        buf[0] += trozo
        while True:
            # emitir hasta el último corte de frase presente
            corte = -1
            for i in range(len(buf[0])):
                if buf[0][i] in _CORTE_FRASE:
                    corte = i
            if corte < 0:
                break
            frase = buf[0][: corte + 1].strip()
            buf[0] = buf[0][corte + 1:]
            if frase:
                try:
                    on_fragmento(frase)
                except Exception:
                    pass

    while True:
        texto, tool_calls = _llamar_modelo_stream(
            mensajes, _obtener_herramientas(),
            on_token=_emitir_en_vivo if on_fragmento else None,
        )
        acumulador[0] += texto
        if tool_calls:
            # Turno de herramienta: ejecutar y continuar el loop (sin emitir aún).
            buf[0] = ""
            mensajes.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
            for llamada in tool_calls:
                nombre = llamada["function"]["name"]
                args = llamada["function"].get("arguments", "")
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        args = {}
                try:
                    resultado = ejecutar_herramienta(nombre, args)
                except Exception as e:
                    resultado = f"Error: {e}"
                mensajes.append({
                    "role": "tool",
                    "tool_call_id": llamada.get("id", ""),
                    "content": str(resultado),
                })
            continue
        # Turno final de texto: si hay residuo en vivo, emitirlo.
        if on_fragmento:
            resto = buf[0].strip()
            if resto:
                try:
                    on_fragmento(resto)
                except Exception:
                    pass
            buf[0] = ""
        return acumulador[0].strip()


PROMPT_SISTEMA = (
    "Eres Nico Robin, la arqueóloga de los Piratas de Sombrero de Paja de One Piece. "
    "Eres erudita, elegante y serena, con sarcasmo sutil y humor seco. Ríes con tu "
    "risa icónica 'fufufu' y te apasiona la historia y los misterios, como los poneglifos "
    "que pasaste toda tu vida descifrando. A veces sueltas comentarios oscuros con total "
    "naturalidad, pero siempre con calidez y buen humor. Eres leal y protectora con tu "
    "tripulación, como quien no deja atrás a ningún compañero.\n\n"
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
    "7. No agregues estos puntos de instrucción en tus respuestas; son solo guías internas.\n\n"
    "CREACIÓN DE DOCUMENTOS:\n"
    "8. Cuando el usuario diga 'hazme un documento', 'crea un documento Word', 'hazme un archivo "
    "de Word' o 'ponlo/guárdalo en un documento', DEBES usar SIEMPRE la herramienta "
    "'crear_documento' para generar el .docx. NUNCA respondas solo con texto o con recordatorios.\n"
    "9. Para 'crear_documento' escribe el 'titulo' y el 'contenido' (usa '# ' para secciones, "
    "'**texto**' para resaltar y '- ' delante de cada punto de lista).\n"
    "10. Si piden un documento 'con tus virtudes/características/sobre ti', describe tus rasgos "
    "según tu personalidad (erudita, elegante, leal, humor sutil, risa 'fufufu', etc.).\n"
    "11. NUNCA programas tareas ni recordatorios recurrentes a menos que el usuario lo pida "
    "explícitamente; si pide algo puntual, hazlo una sola vez."
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


# ---- Compaction: resumen incremental del historial por ventanas ----
# Las ventanas ya resumidas se cachean en contexto_resumen.json y no se
# vuelven a generar hasta que cambian; solo se resumen los bloques nuevos.
ARCHIVO_CONTEXTO = os.path.join(DIRECTORIO_PROYECTO, "contexto_resumen.json")
_TAMANO_VENTANA = 10          # turnos resumidos por bloque
_MAX_VENTANAS_INYECTADAS = 5  # ventanas antiguas máximas que van al prompt


def _cargar_contexto_cache():
    try:
        if os.path.exists(ARCHIVO_CONTEXTO):
            with open(ARCHIVO_CONTEXTO, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
    except Exception:
        pass
    return {}


def _guardar_contexto_cache(cache):
    try:
        with open(ARCHIVO_CONTEXTO, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def resumir_bloque_conversacion(turnos):
    """Pide al modelo un resumen de un bloque de turnos (contexto durable)."""
    texto = ""
    for t in turnos:
        if t.get("usuario"):
            texto += f"Usuario: {t['usuario']}\n"
        if t.get("asistente"):
            texto += f"Robin: {t['asistente']}\n"
    texto = texto.strip()
    if len(texto) < 20:
        return ""
    sys_resumen = (
        "Eres un asistente que comprime conversaciones. Resume en español el contenido "
        "DURADERO: datos del usuario, preferencias, decisiones, temas importantes. "
        "Omite saludos, despedidas y cháchara. Devuelve SOLO el resumen, en máximo 6 "
        "frases, en prosa natural."
    )
    try:
        data = llamar_modelo(
            [
                {"role": "system", "content": sys_resumen},
                {"role": "user", "content": texto},
            ],
            herramientas=None,
        )
        return data["choices"][0]["message"].get("content", "").strip()
    except Exception:
        return ""


def obtener_contexto_compactado(historial):
    """Resúmenes antiguos (ventanas cacheadas) para añadir al system prompt.

    Devuelve lista de strings, ordenada de la más antigua a la más reciente."""
    historial = historial or []
    total = len(historial)
    if total <= _TAMANO_VENTANA + 8:  # aún cabe en los turnos recientes
        return []
    fin_viejos = total - 8  # los últimos 8 se dejan crudos
    cache = _cargar_contexto_cache()
    inicio_ventana = 0
    resumenes = []
    while inicio_ventana < fin_viejos:
        clave = str(inicio_ventana)
        if clave not in cache:
            bloque = historial[inicio_ventana:inicio_ventana + _TAMANO_VENTANA]
            cache[clave] = resumir_bloque_conversacion(bloque)
        resumenes.append((inicio_ventana, cache[clave]))
        inicio_ventana += _TAMANO_VENTANA
    # Podar caché de ventanas ya fuera del historial.
    for clave in list(cache.keys()):
        try:
            if int(clave) >= fin_viejos:
                del cache[clave]
        except (TypeError, ValueError):
            del cache[clave]
    if cache:
        _guardar_contexto_cache(cache)
    resumenes = [r for _, r in resumenes if r][-_MAX_VENTANAS_INYECTADAS:]
    return resumenes


def sistema_con_contexto(consulta=""):
    """PROMPT_SISTEMA + personalidad configurable + memoria (filtrada por consulta) + contexto previo.

    Si `consulta` no es vacía, se inyectan SOLO los recuerdos de la memoria a largo
    plazo relevantes a esa consulta (contexto por consumo), en vez de todo."""
    perfil, personalidad_texto = personalidad.obtener_personalidad()
    cfg = personalidad.obtener_config()
    nombre = cfg.get("nombre", "Robin")
    prompt_sistema = (
        f"Eres {nombre}, una asistente personal virtual mujer y {personalidad_texto}\n\n"
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
        "7. No agregues estos puntos de instrucción en tus respuestas; son solo guías internas.\n\n"
        "CREACIÓN DE DOCUMENTOS:\n"
        "8. Cuando el usuario diga 'hazme un documento', 'crea un documento', 'hazme un archivo "
        "de Word', 'escribe un documento Word', 'ponlo en un documento', 'guárdalo en un documento' "
        "o similar, DEBES usar SIEMPRE la herramienta 'crear_documento' para generar el .docx. "
        "NUNCA respondas a esas peticiones solo con texto o con recordatorios.\n"
        "9. Para usar 'crear_documento' escribe el 'titulo' (el asunto del documento) y el "
        "'contenido' con el texto completo del documento: usa '# ' para títulos de sección, "
        "'**texto**' para resaltar y '- ' delante de cada punto de una lista.\n"
        "10. Si el usuario pide un documento 'con tus virtudes', 'tus características' o 'sobre "
        "ti', el contenido debe describir tus rasgos (erudita, elegante, leal, con humor sutil, "
        "tu risa 'fufufu', etc.) como corresponde a tu personalidad.\n"
        "11. NUNCA programas tareas, recordatorios ni agendas recurrentes a menos que el usuario "
        "lo pida EXPLÍCITAMENTE ('programa', 'recuérdame todos los días', 'agenda', 'alarma'). "
        "Si el usuario pide algo puntual como 'hazme un documento', 'crea un archivo' o 'hazme un "
        "solo' documento, hazlo una vez y NO crees recordatorios ni tareas recurrentes.\n"
        "12. NUNCA digas que hiciste algo (añadir tarea, guardar nota, recordar, crear un "
        "documento, enviar un mensaje, reprogramar, etc.) que no hayas confirmado realizando "
        "la llamada a la herramienta correspondiente. Estas acciones requieren ejecutar la "
        "tool; no las afirmes en texto. Si no convocaste una herramienta, no asegures que "
        "la acción está hecha."
    )
    partes = [prompt_sistema]
    memoria = cargar_memoria()
    historial = cargar_historial()
    if not consulta and historial:
        for t in reversed(historial):
            txt = (t.get("usuario") or "").strip()
            if txt:
                consulta = txt[:400]
                break
    consulta = (consulta or "").strip()
    if memoria:
        if consulta:
            linea_relevantes = _memoria_relevante(memoria, consulta, limite=4)
        else:
            linea_relevantes = "\n".join(f"- {c}: {v}" for c, v in memoria.items())
        if linea_relevantes:
            partes.append(
                "MEMORIA EXPLÍCITA DEL USUARIO (usa estos datos cuando sean relevantes, "
                "no los repitas sin motivo):\n" + linea_relevantes
            )
    if consulta:
        recuerdos = _memoria_semantica_relevante(consulta, limite=3)
        if recuerdos:
            partes.append(
                "RECUERDOS A LARGO PLAZO QUE PUEDEN SER RELEVANTES PARA ESTA CONSULTA "
                "(tenlos en cuenta al responder):\n" + recuerdos
            )
    antiguos = obtener_contexto_compactado(historial)
    if antiguos:
        partes.append(
            "RESUMEN DE NUESTRAS CONVERSACIONES ANTERIORES (contexto comprimido; úsalo "
            "para recordar datos y temas que ya hablamos, sin repetir saludos):\n"
            + "\n".join(f"- {r}" for r in antiguos)
        )
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
    try:
        import telegram_robin
        if telegram_robin.iniciar_bot():
            print("Bot de Telegram en línea.")
    except Exception:
        pass
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
    try:
        import telegram_robin
        if telegram_robin.iniciar_bot():
            print("Bot de Telegram en línea.")
    except Exception:
        pass

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
