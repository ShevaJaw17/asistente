# Funciones compartidas entre el asistente y las tools (red, portapapeles,
# normalización de idiomas). Se aíslan aquí para evitar importaciones
# circulares entre asistente.py y el paquete tools/.

import ctypes
import re
import urllib.parse

import httpx

CLIENTE_WEB = httpx.Client(timeout=httpx.Timeout(20.0), headers={"User-Agent": "Mozilla/5.0"})


def copiar_portapapeles_windows(texto):
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    data = texto.encode("utf-16-le") + b"\x00\x00"

    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    user32.OpenClipboard(None)
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            raise OSError("GlobalAlloc devolvió NULL")
        p = kernel32.GlobalLock(h)
        if not p:
            raise OSError("GlobalLock devolvió NULL")
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        ctypes.memmove(p, buf, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()


def normalizar_idioma(idioma):
    idioma = str(idioma or "").strip().lower()
    equivalencias = {
        "es": "es", "español": "es", "espanol": "es", "castellano": "es",
        "en": "en", "inglés": "en", "ingles": "en", "english": "en",
        "fr": "fr", "francés": "fr", "frances": "fr", "français": "fr",
        "de": "de", "alemán": "de", "aleman": "de",
        "it": "it", "italiano": "it",
        "pt": "pt", "portugués": "pt", "portugues": "pt",
        "ja": "ja", "japonés": "ja", "japones": "ja",
        "zh": "zh", "chino": "zh", "chino simplificado": "zh",
        "ko": "ko", "coreano": "ko",
        "ru": "ru", "ruso": "ru",
        "ar": "ar", "árabe": "ar", "arabe": "ar",
    }
    if idioma in ("auto", "autodetect", "detectar"):
        return "autodetect"
    return equivalencias.get(idioma, idioma)


def buscar_en_internet_impl(consulta):
    url = "https://html.duckduckgo.com/html/"
    try:
        resp = CLIENTE_WEB.post(url, data={"q": consulta})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return f"Error al buscar en internet: {e}"
    bloques = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    if not bloques:
        return "No se encontraron resultados."
    resultados = []
    for href, titulo in bloques[:6]:
        if "uddg=" in href:
            href = urllib.parse.unquote(
                re.search(r"uddg=([^&]+)", href).group(1)
            )
        titulo_limpio = re.sub(r"<[^>]+>", "", titulo).strip()
        resultados.append(f"- {titulo_limpio}\n  {href}")
    return "\n".join(resultados)


def traducir_impl(texto, origen, destino):
    url = ""
    try:
        resp = CLIENTE_WEB.get(
            "https://api.mymemory.translated.net/get",
            params={"q": texto, "langpair": f"{origen}|{destino}"},
        )
        resp.raise_for_status()
        datos = resp.json()
        traduccion = datos.get("responseData", {}).get("translatedText")
        if not traduccion:
            return "Error: el servicio de traducción no devolvió resultado."
        return traduccion
    except Exception:
        return f"Error al traducir: {traducir_impl.__name__} no disponible"
