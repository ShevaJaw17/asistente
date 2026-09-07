# Benchmark de tool calls del asistente.
#
# Prueba las instrucciones más habituales contra el modelo activo del servidor
# llama.cpp y reporta si se invocó la herramienta esperada y con qué argumentos.
#
# Uso:
#   python benchmark_tools.py                     # modelo activo del servidor
#   python benchmark_tools.py --modelos 3b,7b     # pasa por ambos (requiere reconfigurar servidor)
#   python benchmark_tools.py --temp 0.3 --it 2
import argparse
import json
import sys
from collections import Counter

sys.path.insert(0, __file__ and ".")
import asistente  # noqa: E402

# (instrucción, tool esperada, es_tool obligatoria)
PRUEBAS = [
    ("Hazme el resumen del día", "resumen_diario", True),
    ("¿Qué tiempo hace en Madrid?", "clima", True),
    ("Hazme un documento en Word con tus virtudes", "crear_documento", True),
    ("Crea un documento .docx contando lo que quieras sobre ti", "crear_documento", True),
    ("Agenda una llamada para mañana a las 12:00 con el nombre 'revisión'", "agregar_agenda_recurrente", True),
    ("Recuérdame todos los días desayunar a las 8:00", "agregar_agenda_recurrente", True),
    ("Guarda una nota rápida: el Wi-Fi de casa es llave123", "agregar_nota", True),
    ("Añade la tarea 'comprar leche'", "agregar_tarea", True),
    ("Traduce 'good morning' a español", "traducir", True),
    ("¿Qué hora es?", "hora_actual", True),
    ("Recuerda que mi cumpleaños es el 15 de mayo", "recordar_a_largo_plazo", True),
    ("Muéstrame mis recuerdos", "listar_recuerdos", True),
    ("Busca en internet el precio de la RTX 5060", "buscar_en_internet", True),
    ("Abre la calculadora", "abrir_app", False),
]


def _extraer_args(args_raw):
    if isinstance(args_raw, str) and args_raw.strip():
        try:
            return json.loads(args_raw)
        except Exception:
            return {"_raw": args_raw}
    return args_raw or {}


def probar_modelo(modelo="qwen2.5-7b", temperatura=0.3, iteraciones=2, tools=None):
    """Ejecuta las PRUEBAS contra el servidor y devuelve resultados."""
    sys_prompt = asistente.sistema_con_contexto()
    if tools is None:
        tools = asistente._obtener_herramientas()
    resultados = []
    for i in range(iteraciones):
        for instruccion, esperada, obligatoria in PRUEBAS:
            payload = {
                "model": modelo,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": instruccion},
                ],
                "max_tokens": 512,
                "temperature": temperatura,
                "tools": tools,
            }
            try:
                import httpx

                c = httpx.Client(timeout=httpx.Timeout(180.0))
                m = c.post("http://127.0.0.1:8080/v1/chat/completions", json=payload)
                msg = m.json()["choices"][0]["message"]
                tc = msg.get("tool_calls") or []
                nombres = [t["function"]["name"] for t in tc]
                args_list = [_extraer_args(t["function"].get("arguments")) for t in tc]
                resultados.append(
                    {
                        "instruccion": instruccion,
                        "esperada": esperada,
                        "obligatoria": obligatoria,
                        "llamadas": nombres,
                        "args": args_list,
                        "ok": esperada in nombres,
                    }
                )
            except Exception as e:
                resultados.append(
                    {"instruccion": instruccion, "esperada": esperada,
                     "llamadas": [f"ERROR: {e}"], "args": [], "ok": False, "obligatoria": obligatoria}
                )
    return resultados


def resumir(resultados, modelo, temperatura):
    """Imprime un reporte por caso + puntuación global."""
    aciertos = sum(1 for r in resultados if r["ok"])
    if "ERROR" in str(resultados[0]["llamadas"]) and len(resultados) == 1:
        pass
    print()
    print(f"=== Resultados: modelo={modelo} temp={temperatura} ({len(resultados)} pruebas) ===")
    por_caso = {}
    for r in resultados:
        clave = r["instruccion"]
        por_caso.setdefault(clave, []).append(r)
    for instruccion, lista in por_caso.items():
        esperada = lista[0]["esperada"]
        llamadas = Counter()
        muestras_args = []
        for r in lista:
            llamadas.update(r["llamadas"])
            if r["args"]:
                muestras_args.append(r["args"])
        cadena = ", ".join(f"{k}x{v}" for k, v in llamadas.items())
        marca = "OK" if esperada in llamadas else "FALLO"
        print(f"  [{marca}] {instruccion[:45]:47} esperada={esperada:28} llamadas={cadena}")
        if esperada not in llamadas and muestras_args:
            print(f"        args de primera llamada: {json.dumps(muestras_args[0], ensure_ascii=False)[:120]}")
    total_casos = len({r['instruccion'] for r in resultados})
    casos_ok = len({r['instruccion'] for r in resultados if r['ok']})
    print(f"\n  PUNTUACIÓN: {casos_ok}/{total_casos} casos correctos ({round(100*casos_ok/total_casos)}%)")
    return casos_ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Benchmark de tool calls del asistente.")
    ap.add_argument("--modelo", default="qwen2.5-7b", help="Nombre a mostrar (informacional).")
    ap.add_argument("--temp", type=float, default=0.3, help="Temperatura para las pruebas.")
    ap.add_argument("--it", type=int, default=2, help="Iteraciones por instrucción.")
    args = ap.parse_args()

    print(f"Benchmark contra el servidor en http://127.0.0.1:8080")
    print(f"Modelo servido: el activo del servidor (se presenta como {args.modelo})")
    resultados = probar_modelo(
        modelo=args.modelo, temperatura=args.temp, iteraciones=args.it
    )
    resumir(resultados, args.modelo, args.temp)