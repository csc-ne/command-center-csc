"""Email service using SMTP (Gmail / Google Workspace)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings

logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP. Returns True on success."""
    if not settings.FI_SMTP_USER or not settings.FI_SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.FI_SMTP_FROM_NAME} <{settings.FI_SMTP_FROM_EMAIL or settings.FI_SMTP_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        port = settings.FI_SMTP_PORT
        if port == 465:
            # SSL direto (porta 465) — usado quando a rede bloqueia 587
            with smtplib.SMTP_SSL(settings.FI_SMTP_HOST, port, timeout=15) as server:
                server.login(settings.FI_SMTP_USER, settings.FI_SMTP_PASSWORD)
                server.sendmail(msg["From"], [to], msg.as_string())
        else:
            # STARTTLS (porta 587)
            with smtplib.SMTP(settings.FI_SMTP_HOST, port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.FI_SMTP_USER, settings.FI_SMTP_PASSWORD)
                server.sendmail(msg["From"], [to], msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_verification_code(to_email: str, code: str) -> bool:
    """Send the 6-digit verification code to the user."""
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #4f46e5; margin-bottom: 8px;">Fleet Intelligence</h2>
        <p>Seu codigo de verificacao:</p>
        <div style="background: #f1f5f9; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e293b;">{code}</span>
        </div>
        <p style="color: #64748b; font-size: 14px;">
            Este codigo expira em <strong>15 minutos</strong>.<br>
            Se voce nao solicitou este cadastro, ignore este email.
        </p>
    </div>
    """
    return _send_email(to_email, f"Codigo de verificacao: {code}", html)


def send_admin_approval_request(user_email: str, user_full_name: str) -> bool:
    """Notify admin that a new user needs approval."""
    approve_url = f"{settings.FRONTEND_URL}/admin/users"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #4f46e5; margin-bottom: 8px;">Fleet Intelligence</h2>
        <p>Um novo usuario verificou seu email e aguarda aprovacao:</p>
        <div style="background: #f1f5f9; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 4px 0;"><strong>Nome:</strong> {user_full_name}</p>
            <p style="margin: 4px 0;"><strong>Email:</strong> {user_email}</p>
        </div>
        <p>
            <a href="{approve_url}"
               style="display: inline-block; background: #4f46e5; color: #fff; padding: 10px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: 600;">
                Revisar no Fleet Intelligence
            </a>
        </p>
    </div>
    """
    return _send_email(settings.FI_ADMIN_EMAIL, f"Novo cadastro aguardando aprovacao: {user_full_name}", html)


def send_approval_notification(to_email: str, user_full_name: str) -> bool:
    """Notify user that their account was approved."""
    login_url = f"{settings.FRONTEND_URL}/login"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #4f46e5; margin-bottom: 8px;">Fleet Intelligence</h2>
        <p>Ola, <strong>{user_full_name}</strong>!</p>
        <p>Sua conta foi <strong style="color: #16a34a;">aprovada</strong> pelo administrador.
           Voce ja pode acessar a plataforma:</p>
        <p>
            <a href="{login_url}"
               style="display: inline-block; background: #4f46e5; color: #fff; padding: 10px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: 600;">
                Acessar Fleet Intelligence
            </a>
        </p>
    </div>
    """
    return _send_email(to_email, "Sua conta foi aprovada! - Fleet Intelligence", html)


def send_rejection_notification(to_email: str, user_full_name: str) -> bool:
    """Notify user that their account was rejected."""
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #4f46e5; margin-bottom: 8px;">Fleet Intelligence</h2>
        <p>Ola, <strong>{user_full_name}</strong>,</p>
        <p>Infelizmente sua solicitacao de acesso ao Fleet Intelligence nao foi aprovada.
           Se voce acredita que isso foi um erro, entre em contato com o administrador.</p>
    </div>
    """
    return _send_email(to_email, "Solicitacao de acesso - Fleet Intelligence", html)


def send_task_assignment_alert(to_email: str, user_full_name: str,
                                card_title: str, board_name: str) -> bool:
    """Notify user that a card was assigned to them."""
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #4f46e5; margin-bottom: 8px;">Fleet Intelligence</h2>
        <p>Ola, <strong>{user_full_name}</strong>,</p>
        <p>Uma atividade foi atribuida a voce e precisa de atencao:</p>
        <div style="background: #f1f5f9; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 4px 0;"><strong>Card:</strong> {card_title}</p>
            <p style="margin: 4px 0;"><strong>Fluxo:</strong> {board_name}</p>
        </div>
        <p>
            <a href="{settings.FRONTEND_URL}/boards"
               style="display: inline-block; background: #4f46e5; color: #fff; padding: 10px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: 600;">
                Ver no Fleet Intelligence
            </a>
        </p>
    </div>
    """
    return _send_email(to_email, f"Nova atividade atribuida: {card_title}", html)
