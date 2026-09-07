# Roadmap — Asistente Nico Robin

Plan de trabajo priorizado para el asistente virtual local (Python + llama.cpp + GPU Vulkan).

## Estado actual (referencia)

| Área | Hoy |
|------|-----|
| Modelo | qwen2.5-3b (llama.cpp, Vulkan/GPU AMD, `-c 16384`) |
| Herramientas | 68 tools registradas (agenda, archivos, clima, documentos, memoria, notas, recordatorios, rutinas, sistema, tareas, utilidades, web...) |
| Voz | TTS: Chatterbox (clonada Robin) / Kokoro / edge-tts. STT: Google (es-MX) |
| Memoria | JSON explícita (`memoria.json`) + semántica ligera TF-IDF (`memoria_semantica.json`) + historial |
| Interfaz | Tkinter (texto + voz + micrófono) con avatar Live2D/VTube |
| Web | servidor FastAPI (puerto 8000) para chat desde el celular |
| Automatización | cron local (`programador.py`), proactividad (saludos/avisos), rutinas |

---

## Fase 1 — Inteligencia y modelo (P0)

Objetivo: que Robin entienda mejor las instrucciones y falle menos en la selección de herramientas.

- [ ] **Probar modelos superiores** manteniendo la GPU (AMD Vulkan):
  - qwen2.5-7b-instruct Q4_K_M (sube ~5 % VRAM, gana precisión de tools).
  - qwen3-8b / qwen3-4b si la GPU lo permite (mejor seguimiento de instrucciones).
  - Documentar resultados comparando: tasa de acierto en tool calls y latencia.
- [ ] **Benchmark de tools**: script que pruebe las 10 instrucciones más habituales ("resumen del día", "hazme un documento...", "programa que...") y detecte cuándo el modelo llama a la tool equivocada.
- [ ] **Namespacing/descripciones de tools**: revisar descripciones ambiguas que hacen que el modelo confunda herramientas (ej: TTS vs STT, recordatorio vs documento). Hacer las descripciones más disuasorias/explícitas.
- [ ] **Fallback de tool calls inválidas**: si el modelo genera `arguments` corruptos o una tool desconocida, reintentar el turno indicándole el error en vez de cortar la conversación.
- [ ] **Manejo de multi-tool**: permitir que una respuesta ejecute varias tools en paralelo (ya lo soporta en parte) y validar su orden.
- [ ] **Selección dinámica de tools**: pasar al modelo solo las tools «activas» más probables por intención, reduciendo el prompt y el ruido (hoy van las 68 siempre → ~8k tokens).

## Fase 2 — Memoria y contexto (P1)

Objetivo: que recuerde con precisión y resuma conversaciones largas sin desbordar contexto.

- [x] **Embeddings semánticos reales** para `memoria_semantica.py`: sustituir TF-IDF por sentence-transformers (modelo pequeño en CPU, ej. `paraphrase-multilingual-MiniLM`), con caché de vectores en disco.
- [x] **Compaction / resumen automático**: cuando el historial de la sesión supere N mensajes, pedir al modelo un resumen y reemplazar los mensajes viejos.
- [x] **Consolidación de memoria**: al terminar cada sesión, extraer hechos nuevos con el modelo y fusionarlos en `memoria.json` (evitar duplicados, priorizar datos recientes).
- [x] **Recuerdos priorizados**: semanas/prioridad en `memoria_semantica.json` y exponerlo en `recuperar_recuerdos`.
- [x] **Memoria por contexto**: que la memoria se inyecte **dentro** del system prompt solo cuando sea relevante a la consulta actual (hoy va siempre completa).
- [x] **Borrado/edición de recuerdos desde el chat**: tool `editar_recuerdo` (hoy solo `olvidar` por clave).

## Fase 3 — Voz y audio (P1)

Objetivo: voz natural, sin depender de la nube, y sin cortes al dictar.

- [x] **STT local opcional**: Vosk (local, sin internet) instalado con modelo es-0.3 en `data/vosk/`; campo `motor_stt: auto|google|vosk` en `voz_config.json`; Google como fallback automático si no hay modelo.
- [x] **Bloqueo de doble audio**: `hay_voz_activa()` + `detener_voz()` al pulsar "Hablar", y al escribir cualquier tecla en la caja de texto.
- [x] **Cache de TTS**: audios por hash del texto en `data/cache_voz/` (límite 200 archivos, purga por antigüedad); frases repetidas ya no se resintetizan en CPU (13.6s → 1.9s probado).
- [x] **Detener habla al escribir**: botón "Parar voz" + atajo `F8` + auto-interrupción al teclear.
- [x] **Config de dictado en `voz_config.json`**: tool `configurar_dictado` (duración/silencio/motor) + botón "Dictado" en la GUI; `aplicar_config()` de `voz.py` recarga la config **en vivo** sin reiniciar (también el cambio de voz).
- [x] **Mejorar voz Chatterbox**: parámetros configurables en `voz_config.json` (`chatterbox_temperature`, `chatterbox_repetition`, `chatterbox_top_p`, `chatterbox_min_p`); default más estable (temp 0.6, top_p 0.9, rep 2.2). Probado con frase larga de 52 palabras (15.2s de audio).

## Fase 4 — Integraciones y productividad (P1/P2)

Objetivo: que Robin genere, reciba y gestione contenido real.

- [x] **Más formatos de documentos**: `crear_documento` ahora soporta `.pdf` (reportlab) y `.xlsx` (openpyxl) además de `.docx`, con el mismo contenido markdown-lite (`;` separa celdas en xlsx).
- [x] **Plantillas de documento**: tool `crear_plantilla` (informe, plan_semanal, curriculum, lista_compra, reunion) que rellena los campos y genera docx/pdf/xlsx; `listar_plantillas` muestra los campos de cada una.
- [x] **Correo**: tools `configurar_correo` (SMTP/IMAP guardado en `data/correo_config.json`), `enviar_correo` (con confirmación obligatoria) y `leer_correo` (IMAP, últimos N mensajes).
- [x] **WhatsApp/Telegram**: bot Telegram (`telegram_robin.py`, long polling con httpx): historial por chat persistido, memoria por contexto y tools completas; se arranca con la GUI, el servidor web o el modo CLI si hay token. Tools `configurar_telegram`, `estado_telegram`, `iniciar/detener`, `quitar_acceso`. Token en `data/telegram_config.json`; auto-autoriza al primer usuario.
- [x] **Calendario externo**: tool `exportar_agenda_ics` exporta la agenda recurrente a `.ics` importable en Google Calendar / Outlook.
- [x] **Control de música**: tool `controlar_musica` con teclas multimedia del sistema (play/pause, siguiente, anterior, volumen, silencio); funciona con cualquier reproductor (Spotify, MPC...).
- [x] **Exportar datos**: tool `exportar_datos` a `.csv`/`.xlsx`/`.docx`/`.pdf`/`.txt` (tareas, notas, recuerdos, memoria, recordatorios, agenda o todo).

## Fase 5 — UI/UX y avatar (P2)

Objetivo: interfaz más cuidada y avatar más vivo.

- [x] **Indicadores de estado en GUI**: barra de estado con tres lámparas luminosas (Pensando/Hablando/Grabando con pulso suave) además del texto con color; el estado "Hablando…" se enciende solo mientras el TTS reproduce audio vía `_monitorizar_voz`.
- [ ] **Botón de interrupción**: detener la respuesta/la voz en curso desde la GUI.
- [ ] **Tema claro/oscuro** y fuente configurable en la interfaz.
- [ ] **Panel de configuración**: vista gráfica para cambiar personalidad, voz, idioma STT y duración de dictado (sin necesidad de recordar los comandos de chat).
- [ ] **Avatar**: sincronizar gestos/movimientos del Live2D con el estado del habla; probar `avatar_nativo.py` como reemplazo sin VTube Studio.
- [x] **Accesos rápidos**: barra de botones en la cabecera (Clima, Resumen del día, Tareas, Notas, Recordatorios, Agenda) + **Nueva nota** y **Documento** que piden el contenido con un diálogo antes de enviar el comando a Robin.
- [ ] **Web mejorada**: streaming de texto/voz en el chat web y acceso con PIN para uso remoto seguro.

---

### Notas
- Orden sugerido de ejecución: **F1 → F2 → F3 → F4 → F5** (F1 desbloquea calidad; F2 evita degradación en conversaciones largas).
- Cada item se considera listo cuando hay una herramienta/GUI probada y **no** un cambio solo de prompt.
- Se puede marcar como `[x]` cada ítem al completarlo.