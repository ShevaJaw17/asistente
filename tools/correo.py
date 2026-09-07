# Tool de correo: enviar (SMTP) y leer (IMAP) con confirmación obligatoria.
# Las credenciales se guardan en data/correo_config.json tras configurar_correo.
import os
import json

import tools.asistente_util as util
import tools.registro as reg

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO_CONFIG = os.path.join(_DIR, "data", "correo_config.json")


def _cargar_config():
    try:
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_config(cfg):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_CONFIG), exist_ok=True)
        with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


@reg.registrar(
    "configurar_correo",
    descripcion=(
        "Guarda las credenciales de correo para que Robin pueda enviar y leer "
        "correo. 'direccion' (tú@dominio.com), 'contrasena' o 'contraseña' "
        "('app_password' si tienes verificación en 2 pasos), 'smtp_servidor' y "
        "'smtp_puerto' para enviar, 'imap_servidor' e 'imap_puerto' para leer. "
        "Si solo dai la dirección y contraseña, usa los ajustes típicos de Gmail."
    ),
    parametros={
        "direccion": {"type": "string", "description": "Dirección de correo (tú@dominio.com).", "requerido": True},
        "contrasena": {"type": "string", "description": "Contraseña o app_password.", "requerido": True},
        "smtp_servidor": {"type": "string", "description": "Servidor SMTP saliente (opcional)."},
        "smtp_puerto": {"type": "integer", "description": "Puerto SMTP (opcional)."},
        "imap_servidor": {"type": "string", "description": "Servidor IMAP de entrada (opcional)."},
        "imap_puerto": {"type": "integer", "description": "Puerto IMAP (opcional)."},
    },
)
def configurar_correo(direccion, contrasena, smtp_servidor=None, smtp_puerto=None,
                      imap_servidor=None, imap_puerto=None):
    cfg = _cargar_config()
    cfg["direccion"] = (direccion or "").strip()
    cfg["contrasena"] = contrasena or ""
    dominio = cfg["direccion"].split("@")[-1].lower() if "@" in cfg["direccion"] else ""
    cfg.setdefault("smtp_servidor", smtp_servidor or f"smtp.{dominio}".strip("."))
    cfg.setdefault("smtp_puerto", smtp_puerto or 465)
    cfg.setdefault("imap_servidor", imap_servidor or f"imap.{dominio}".strip("."))
    cfg.setdefault("imap_puerto", imap_puerto or 993)
    if smtp_servidor:
        cfg["smtp_servidor"] = smtp_servidor
    if smtp_puerto:
        cfg["smtp_puerto"] = smtp_puerto
    if imap_servidor:
        cfg["imap_servidor"] = imap_servidor
    if imap_puerto:
        cfg["imap_puerto"] = imap_puerto
    if not _guardar_config(cfg):
        return "No se pudo guardar la configuración de correo."
    return (f"Correo configurado para {cfg['direccion']}.\n"
            f"- SMTP: {cfg['smtp_servidor']}:{cfg['smtp_puerto']}\n"
            f"- IMAP: {cfg['imap_servidor']}:{cfg['imap_puerto']}\n"
            "Ya puedo enviar y leer tu correo. Pídemelo cuando quieras.")


@reg.registrar(
    "enviar_correo",
    descripcion=(
        "Envía un correo por SMTP al destinatario indicado con asunto y cuerpo. "
        "Usa la cuenta configurada. Ej: 'envía un correo a alguien@correo.com con "
        "asunto X y cuerpo que diga Y'. Solicita confirmación si tiene adjuntos o "
        "va a muchos destinatarios."
    ),
    parametros={
        "destinatario": {"type": "string", "description": "Correo(s) de destino (separados por coma).", "requerido": True},
        "asunto": {"type": "string", "description": "Asunto del correo.", "requerido": True},
        "cuerpo": {"type": "string", "description": "Cuerpo del mensaje.", "requerido": True},
    },
    requiere_confirmacion=True,
)
def enviar_correo(destinatario, asunto, cuerpo):
    cfg = _cargar_config()
    if not cfg.get("direccion") or not cfg.get("contrasena"):
        return ("Aún no tengo tu correo configurado. Usa 'configurar_correo' con "
                "tu dirección y contraseña (o app password).")
    if not util.pedir_confirmacion(
            f"¿Envío el correo a {destinatario} con asunto '{asunto}'?"):
        return "Cancelado el envío del correo."
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
    except Exception as e:
        return f"Error importando smtplib: {e}"
    msg = MIMEMultipart()
    msg["From"] = cfg["direccion"]
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    if not destinatario or "," not in destinatario:
        pass  # un solo destinatario no requiere confirmación extra
    try:
        puerto = int(cfg.get("smtp_puerto", 465))
        use_ssl = puerto in (465, 587)
        if use_ssl and puerto == 465:
            servidor = smtplib.SMTP_SSL(cfg["smtp_servidor"], puerto, timeout=30)
        else:
            servidor = smtplib.SMTP(cfg["smtp_servidor"], puerto, timeout=30)
        if not (use_ssl and puerto == 465):
            servidor.starttls()
        servidor.login(cfg["direccion"], cfg["contrasena"])
        servidor.sendmail(cfg["direccion"],
                          [d.strip() for d in destinatario.split(",")], msg.as_string())
        servidor.quit()
    except Exception as e:
        return f"No se pudo enviar el correo: {e}"
    return f"Correo enviado a {destinatario} con asunto '{asunto}'."


@reg.registrar(
    "leer_correo",
    descripcion=(
        "Lee los correos más recientes de la bandeja de entrada por IMAP. "
        "'n' cuántos leer (por defecto 5). Muestra remitente, asunto y un extracto."
    ),
    parametros={
        "n": {"type": "integer", "description": "Cuántos correos leer (1-20)."},
    },
)
def leer_correo(n=5):
    cfg = _cargar_config()
    if not cfg.get("direccion") or not cfg.get("contrasena"):
        return ("Aún no tengo tu correo configurado. Usa 'configurar_correo' con "
                "tu dirección y contraseña.")
    n = max(1, min(20, int(n or 5)))
    try:
        import imaplib
        import email
        from email.header import decode_header
    except Exception as e:
        return f"Error importando imaplib: {e}"
    try:
        conn = imaplib.IMAP4_SSL(cfg["imap_servidor"], int(cfg.get("imap_puerto", 993)))
        conn.login(cfg["direccion"], cfg["contrasena"])
        conn.select("INBOX")
        _, ids = conn.search(None, "ALL")
        lista = ids[0].split()
        seleccion = lista[-n:]
        mensajes = []
        for num in reversed(seleccion):
            _, data = conn.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            remitente = str(email.utils.parseaddr(msg.get("From", ""))[1] or msg.get("From", ""))
            asunto = _decodificar(msg.get("Subject", ""))
            cuerpo = ""
            partes = msg.walk()
            for parte in partes:
                if parte.get_content_type() == "text/plain" and not parte.get("Content-Disposition"):
                    try:
                        cuerpo = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "ignore").strip()
                    except Exception:
                        cuerpo = ""
                    if not cuerpo:
                        try:
                            cuerpo = parte.get_payload() or ""
                        except Exception:
                            cuerpo = ""
                    break
            if len(cuerpo) > 140:
                cuerpo = cuerpo[:140] + "…"
            mensajes.append(f"- De: {remitente}\n  Asunto: {asunto}\n  {cuerpo}")
        conn.logout()
    except Exception as e:
        return f"No se pudieron leer los correos: {e}"
    if not mensajes:
        return "No hay correos en la bandeja de entrada."
    return "Últimos correos:\n\n" + "\n\n".join(mensajes)


def _decodificar(texto):
    try:
        from email.header import decode_header
        partes = decode_header(texto or "")
        return "".join(
            p.decode(c if isinstance(c, str) else "utf-8") if isinstance(p, bytes) else p
            for p, c in partes
        )
    except Exception:
        return texto or ""