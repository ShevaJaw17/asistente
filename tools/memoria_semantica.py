# Memoria semántica a largo plazo (ligera, numpy puro, sin dependencias externas).
#
# Guarda hechos/frases en "memoria_semantica.json" y permite buscarlos por
# similitud de términos (peso TF-IDF + coseno). Suficiente para recordar
# preferencias, datos y frases clave sin instalar embeddings ni modelos pesados.
import json
import math
import os
import re
from datetime import datetime

import numpy as np

import tools.asistente_util as util

ARCHIVO = os.path.join(util.DIRECTORIO_PROYECTO, "memoria_semantica.json")

# Palabras vacías en español (mínimas; suficiente para este índice ligero).
_VACIAS = set(
    """de la que el en y a los del se las por un para con no una su al lo
    como más mas pero sus le ya o este sí sin porque todo también me hasta hay
    donde quien desde todo nos dos cuando mucho si bien este ese esa eso estas
    estos esta está están son era tiene tengo había ti mi mis tu tus""".split()
)

_RAROS = re.compile(r"[^\wáéíóúñüÁÉÍÓÚÑÜ]+", re.UNICODE)


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


def recordar(frase, etiqueta=None):
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
            _guardar(datos)
            return f"Añadido lectura al recuerdo ya existente: {frase}"
    datos.append(
        {
            "texto": frase,
            "etiqueta": (etiqueta or "").strip() or None,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    _guardar(datos)
    return f"Recordado a largo plazo: {frase}"


def recuerdos():
    datos = _cargar()
    if not datos:
        return "No tengo recuerdos a largo plazo guardados."
    return "\n".join(
        f"- [{h.get('fecha', '?')}] {h['texto']}"
        f"{(' (' + h['etiqueta'] + ')') if h.get('etiqueta') else ''}"
        for h in reversed(datos)
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


def buscar(consulta, limite=3, umbral=0.05):
    """Devuelve los recuerdos más relevantes a una consulta por similitud de términos."""
    consulta = (consulta or "").strip()
    if not consulta:
        return ""
    datos = _cargar()
    if not datos:
        return ""
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
