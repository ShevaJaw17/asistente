# Memoria semántica a largo plazo (embeddings reales con fallback TF-IDF).
#
# Guarda hechos/frases en "memoria_semantica.json". Para buscar usa embeddings
# semánticos (sentence-transformers, multilingüe) cuando están disponibles, con
# caché de vectores en disco; si no, cae al índice TF-IDF ligero de siempre.
import hashlib
import json
import math
import os
import re
from datetime import datetime

import numpy as np

import tools.asistente_util as util

ARCHIVO = os.path.join(util.DIRECTORIO_PROYECTO, "memoria_semantica.json")
_CACHE_EMBEDDINGS = os.path.join(util.DIRECTORIO_PROYECTO, "data", "embeddings_cache.json")

# Palabras vacías en español (mínimas; suficiente para este índice ligero).
_VACIAS = set(
    """de la que el en y a los del se las por un para con no una su al lo
    como más mas pero sus le ya o este sí sin porque todo también me hasta hay
    donde quien desde todo nos dos cuando mucho si bien este ese esa eso estas
    estos esta está están son era tiene tengo había ti mi mis tu tus""".split()
)

_RAROS = re.compile(r"[^\wáéíóúñüÁÉÍÓÚÑÜ]+", re.UNICODE)

# Encoder perezoso (solo se carga la primera vez que se usa una búsqueda).
_modelo_emb = None
_modelo_emb_error = None
# Cache de vectores en memoria: hash_texto -> [dims]
_cache_vec_mem = {}


def _obtener_modelo_emb():
    """Devuelve el encoder de sentence-transformers o None si no está disponible."""
    global _modelo_emb, _modelo_emb_error
    if _modelo_emb is not None or _modelo_emb_error:
        return _modelo_emb
    try:
        from sentence_transformers import SentenceTransformer
        _modelo_emb = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception as e:  # noqa: BLE001
        _modelo_emb_error = str(e)
        return None
    return _modelo_emb


def _hash_texto(texto):
    return hashlib.md5((texto or "").encode("utf-8")).hexdigest()


def _cargar_cache_vec_disco():
    try:
        if os.path.exists(_CACHE_EMBEDDINGS):
            with open(_CACHE_EMBEDDINGS, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                _cache_vec_mem.update(d)
    except Exception:
        pass


def _guardar_cache_vec_disco():
    try:
        d = os.path.dirname(_CACHE_EMBEDDINGS)
        os.makedirs(d, exist_ok=True)
        with open(_CACHE_EMBEDDINGS, "w", encoding="utf-8") as f:
            json.dump(_cache_vec_mem, f, ensure_ascii=False)
    except Exception:
        pass


def _embed(textos):
    """Devuelve matriz (n, dim) con los vectores de `textos` usando caché en disco.

    Si el encoder no está disponible devuelve una matriz vacía (0, 0)."""
    _cargar_cache_vec_disco()
    faltan_idx, faltan_textos = [], []
    for i, t in enumerate(textos):
        clave = _hash_texto(t)
        if clave not in _cache_vec_mem:
            faltan_idx.append(i)
            faltan_textos.append(t)
    if faltan_textos:
        modelo = _obtener_modelo_emb()
        if modelo is None:
            return np.zeros((0, 0), dtype=np.float32)
        nuevos = modelo.encode(faltan_textos, normalize_embeddings=True)
        for i, t, vec in zip(faltan_idx, faltan_textos, nuevos):
            _cache_vec_mem[_hash_texto(t)] = [float(x) for x in vec]
        _guardar_cache_vec_disco()
    try:
        return np.stack([np.array(_cache_vec_mem[_hash_texto(t)], dtype=np.float32) for t in textos])
    except Exception:
        return np.zeros((0, 0), dtype=np.float32)


def _buscar_emb(consulta, limite, umbral):
    """Búsqueda por coseno sobre embeddings reales. None si no hay encoder disponible."""
    if _obtener_modelo_emb() is None:
        return None
    datos = _cargar()
    if not datos:
        return ""
    _cargar_cache_vec_disco()
    textos = [d.get("texto", "") for d in datos]
    vecs = _embed(textos + [consulta])
    if vecs.size == 0:
        return ""
    hechos = vecs[: len(datos)]
    vq = vecs[-1]
    scores = hechos @ vq
    # Bonus por prioridad: los recuerdos prioritarios empatan o superan ligeramente.
    bonus = np.array([_BONUS_PRIORIDAD.get((d.get("prioridad") or "media"), 0.0) for d in datos])
    scores = scores + bonus
    orden = np.argsort(scores)[::-1]
    lineas = []
    for idx in orden:
        if scores[idx] >= umbral and len(lineas) < limite:
            lineas.append(f"- {datos[int(idx)]['texto']}")
    return "\n".join(lineas)


def _tokenizar(texto):
    texto = (texto or "").lower()
    tokens = [t for t in _RAROS.split(texto) if t and len(t) > 1 and t not in _VACIAS]
    return tokens


def _cargar():
    try:
        if os.path.exists(ARCHIVO):
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, list):
                    return d
    except Exception:
        pass
    return []


def _guardar(datos):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _df(datos):
    """Frecuencia de documentos: cuántos hechos contienen cada término."""
    df = {}
    for hecho in datos:
        for t in set(_tokenizar(hecho.get("texto", ""))):
            df[t] = df.get(t, 0) + 1
    return df


def _prioridad_default(etiqueta):
    """Asigna prioridad sugerida según la etiqueta/frase."""
    etiqueta = (etiqueta or "").lower()
    if any(k in etiqueta for k in ("importante", "critico", "alerta", "urgencia", "emergencia", "vital")):
        return "alta"
    if any(k in etiqueta for k in ("gusto", "preferencia", "dato", "personal", "contacto", "familia")):
        return "alta"
    return "media"


def _pi(prioridad):
    return {"alta": 0, "media": 1, "baja": 2}.get((prioridad or "media").lower(), 1)


_BONUS_PRIORIDAD = {"alta": 0.06, "media": 0.0, "baja": -0.06}


def recordar(frase, etiqueta=None, prioridad=None):
    """Guarda una frase/hecho como recuerdo a largo plazo."""
    frase = (frase or "").strip()
    if not frase:
        return "Error: no hay nada que recordar."
    datos = _cargar()
    # Evitar duplicados exactos.
    for hecho in datos:
        if hecho.get("texto", "").strip().lower() == frase.lower():
            hecho["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            if etiqueta:
                hecho["etiqueta"] = etiqueta
            if prioridad:
                hecho["prioridad"] = prioridad
            _guardar(datos)
            return f"Añadido lectura al recuerdo ya existente: {frase}"
    datos.append(
        {
            "texto": frase,
            "etiqueta": (etiqueta or "").strip() or None,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "prioridad": prioridad or _prioridad_default(etiqueta),
        }
    )
    _guardar(datos)
    return f"Recordado a largo plazo: {frase}"


def recuerdos():
    datos = _cargar()
    if not datos:
        return "No tengo recuerdos a largo plazo guardados."
    datos = sorted(datos, key=lambda h: (_pi(h.get("prioridad")), h.get("fecha", "")))
    return "\n".join(
        f"- [{h.get('fecha', '?')}] {h['texto']}"
        f"{(' (' + h['etiqueta'] + ')') if h.get('etiqueta') else ''}"
        f"{(' [' + h['prioridad'] + ']') if h.get('prioridad') else ''}"
        for h in datos
    )


def _vector_consulta(consulta, df, n):
    tokens = _tokenizar(consulta)
    v = {}
    for t in tokens:
        v[t] = v.get(t, 0) + 1
    # Peso TF-IDF: tf * log(N/(1+df))
    norm = math.sqrt(sum(c * c for c in v.values()))
    vec = {}
    for t, c in v.items():
        idf = math.log((n + 1) / (1 + df.get(t, 0))) + 1
        vec[t] = (c / norm if norm else 0) * idf
    return vec


def _similitud(v1, v2):
    """Coseno entre dos dicts de término->peso."""
    if not v1 or not v2:
        return 0.0
    producto = 0.0
    for t, w in v1.items():
        if t in v2:
            producto += w * v2[t]
    return producto


def _encontrar_indice(referencia):
    """Localiza el índice (0-based) de un recuerdo por número (1-based) o por texto.

    Acepta:
    - un entero (índice tal y como se ve en listar, 1-based)
    - un texto que coincida exacta o parcialmente con el recuerdo
    - un texto con similitud de términos
    Devuelve (indice, entrada) o (None, None) si no existe.
    """
    datos = _cargar()
    if not datos:
        return None, None
    if isinstance(referencia, int) or (isinstance(referencia, str) and referencia.strip().isdigit()):
        n = int(referencia)
        if 1 <= n <= len(datos):
            return n - 1, datos[n - 1]
        return None, None
    ref = (referencia or "").strip().lower()
    # 1) coincidencia exacta o el texto está contenido en el recuerdo.
    for i, hecho in enumerate(datos):
        texto = hecho.get("texto", "").lower()
        if texto == ref or ref in texto or texto in ref:
            return i, hecho
    # 2) mejor similitud de términos.
    df = _df(datos)
    n = len(datos)
    vq = _vector_consulta(ref, df, n)
    mejor, mejor_sim = -1, 0.0
    for i, hecho in enumerate(datos):
        vh = _vector_consulta(hecho.get("texto", ""), df, n)
        sim = _similitud(vq, vh)
        if sim > mejor_sim:
            mejor_sim, mejor = sim, i
    if mejor >= 0 and mejor_sim > 0.0:
        return mejor, datos[mejor]
    return None, None


def olvidar(referencia):
    """Elimina un recuerdo por índice o por texto parcial. Devuelve mensaje."""
    indice, entrada = _encontrar_indice(referencia)
    if indice is None:
        return f"No encontré ningún recuerdo que coincida con '{referencia}'."
    datos = _cargar()
    eliminado = datos.pop(indice)["texto"]
    _guardar(datos)
    return f"Recordatorio eliminado: {eliminado}"


def editar(referencia, nuevo_texto):
    """Reemplaza el texto de un recuerdo identificado por índice o texto."""
    nuevo_texto = (nuevo_texto or "").strip()
    if not nuevo_texto:
        return "Error: falta el nuevo texto del recuerdo."
    indice, entrada = _encontrar_indice(referencia)
    if indice is None:
        return f"No encontré ningún recuerdo que coincida con '{referencia}'."
    datos = _cargar()
    antiguo = datos[indice]["texto"]
    datos[indice]["texto"] = nuevo_texto
    datos[indice]["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _guardar(datos)
    return f"Recuerdo editado: '{antiguo}' → '{nuevo_texto}'"


def buscar(consulta, limite=3, umbral=0.05):
    """Devuelve los recuerdos más relevantes a una consulta.

    Usa embeddings semánticos reales si están disponibles (umbral ~0.35);
    si no, cae al índice TF-IDF con el umbral indicado."""
    consulta = (consulta or "").strip()
    if not consulta:
        return ""
    datos = _cargar()
    if not datos:
        return ""
    resultado_emb = _buscar_emb(consulta, limite, umbral=0.35)
    if resultado_emb is not None:
        return resultado_emb
    # Fallback: TF-IDF.
    df = _df(datos)
    n = len(datos)
    vq = _vector_consulta(consulta, df, n)
    puntuaciones = []
    for hecho in datos:
        vh = _vector_consulta(hecho.get("texto", ""), df, n)
        sim = _similitud(vq, vh)
        if sim > 0:
            puntuaciones.append((sim, hecho))
    puntuaciones.sort(reverse=True)
    resultado = [h for sim, h in puntuaciones if sim >= umbral][:limite]
    return "\n".join(f"- {h['texto']}" for h in resultado)


def precargar_modelo():
    """Inicia en un hilo de fondo la carga del encoder de embeddings para que la
    primera búsqueda semántica no congele la respuesta. No bloquea."""
    try:
        import threading
        if _modelo_emb is None and not _modelo_emb_error:
            t = threading.Thread(target=_obtener_modelo_emb, daemon=True)
            t.start()
    except Exception:
        pass
