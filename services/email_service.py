"""Outgoing mail for DigiSafe.

One job: get a verification code into the hands of the person who claims an
email address, and report honestly whether that happened.

Two delivery paths, chosen by whether SMTP_HOST is configured:

  * Configured   - the message is handed to a real SMTP server.
  * Unconfigured - the message is written to storage/outbox/ and printed to the
    server console.

The second path exists so the platform is never a dead end. A marker without
internet access, or a developer who has not set up a mailbox, can still
complete a real registration by reading the code off the console. What it
deliberately does NOT do is claim the mail was sent: the caller receives
delivery == "outbox" and the interface tells the user where to look.
"""

import html
import secrets
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from core.config import settings


def generate_verification_code() -> str:
    """A six-digit code, from the OS cryptographic RNG rather than random().

    random() is seeded predictably and its stream can be reconstructed from a
    handful of prior outputs; for anything guarding an account, secrets is the
    only correct source.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_verification_token() -> str:
    """The opaque half, carried by the emailed link."""
    return secrets.token_urlsafe(32)[:64]


def is_smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.MAIL_FROM)


def resolve_base_url(request_base_url: str = "") -> str:
    """Where the emailed link should point.

    A configured APP_BASE_URL always wins - that is what pinning it means, and
    it is what makes a forged Host header harmless on a real deployment. With
    nothing configured, the address the browser actually used is the only one
    known to be reachable, so it is preferred over any guess.
    """
    if settings.APP_BASE_URL:
        return settings.APP_BASE_URL
    if request_base_url:
        return request_base_url.strip().rstrip("/")
    return settings.FALLBACK_BASE_URL


def verification_link(token: str, base_url: str = "") -> str:
    return f"{resolve_base_url(base_url)}/verify?token={token}"


def _build_message(to_email: str, subject: str, text_body: str, html_body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="digisafe.local")
    # Verification mail is transactional. Marking it as such keeps it out of
    # bulk-mail folders and tells any list manager not to treat it as a
    # subscription the recipient may be unsubscribed from.
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _write_to_outbox(message: EmailMessage, to_email: str) -> Path:
    outbox = Path(settings.OUTBOX_DIR)
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    safe_recipient = "".join(ch if ch.isalnum() else "_" for ch in to_email)[:60]
    path = outbox / f"{stamp}_{safe_recipient}.eml"
    path.write_bytes(bytes(message))
    return path


def _send_via_smtp(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.SMTP_SSL:
        server = smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT,
            context=context,
        )
    else:
        server = smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT,
        )
    try:
        server.ehlo()
        if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
            server.starttls(context=context)
            server.ehlo()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()


def _render_bodies(first_name: str, code: str, link: str, minutes: int):
    text_body = (
        f"Hello {first_name},\n\n"
        "Someone - we hope you - just created a DigiSafe account with this "
        "email address.\n\n"
        "Your verification code is:\n\n"
        f"    {code}\n\n"
        "Type it into the verification page to activate your account, or open "
        "this link:\n\n"
        f"{link}\n\n"
        f"The code expires in {minutes} minutes.\n\n"
        "If you did not create this account, ignore this message. The account "
        "cannot be used\nuntil this code is entered, and it will simply lapse.\n\n"
        "--\n"
        "DigiSafe - Digital Safety and Record Protection System\n"
        "Kwame Nkrumah University of Science and Technology\n"
    )

    safe_name = html.escape(first_name)
    safe_link = html.escape(link, quote=True)
    html_body = f"""<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;">
      <tr>
        <td style="background:#0f172a;padding:24px;text-align:center;color:#ffffff;">
          <div style="font-size:20px;font-weight:700;">Digi<span style="color:#22d3ee;">Safe</span></div>
          <div style="font-size:12px;color:#94a3b8;margin-top:4px;">Digital Safety &amp; Record Protection</div>
        </td>
      </tr>
      <tr>
        <td style="padding:28px 24px;">
          <p style="margin:0 0 14px;font-size:15px;">Hello {safe_name},</p>
          <p style="margin:0 0 18px;font-size:15px;line-height:1.55;">
            Someone &mdash; we hope you &mdash; just created a DigiSafe account with this
            email address. Enter the code below to confirm the address is yours.
          </p>
          <div style="margin:0 0 20px;padding:18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;text-align:center;">
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:8px;">Verification code</div>
            <div style="font-size:34px;font-weight:700;letter-spacing:.28em;font-family:Consolas,monospace;color:#0f172a;">{code}</div>
          </div>
          <div style="text-align:center;margin:0 0 20px;">
            <a href="{safe_link}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 26px;border-radius:9px;">Verify my account</a>
          </div>
          <p style="margin:0 0 14px;font-size:13px;color:#475569;line-height:1.55;">
            The code expires in {minutes} minutes. If the button does not work, copy this
            address into your browser:<br>
            <span style="word-break:break-all;color:#2563eb;">{safe_link}</span>
          </p>
          <p style="margin:0;font-size:13px;color:#64748b;line-height:1.55;">
            If you did not create this account, you can ignore this message. The account
            stays locked until this code is entered.
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:16px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;text-align:center;line-height:1.5;">
          DigiSafe &bull; KNUST Department of Computer Science<br>
          Confidentiality protected under the Ghana Data Protection Act 2012 (Act 843)
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return text_body, html_body


def send_verification_email(
    to_email: str, full_name: str, code: str, token: str, base_url: str = ""
) -> dict:
    """Deliver a verification code. Never raises - it reports.

    A mail failure must not undo a registration that already succeeded, so the
    outcome comes back as data for the caller to surface. The account exists
    either way and the code stays valid; the person can ask for another send.
    """
    link = verification_link(token, base_url)
    first_name = (full_name or "").strip().split(" ")[0] or "there"
    minutes = settings.VERIFICATION_CODE_TTL_MINUTES
    text_body, html_body = _render_bodies(first_name, code, link, minutes)

    message = _build_message(
        to_email=to_email,
        subject=f"Your DigiSafe verification code: {code}",
        text_body=text_body,
        html_body=html_body,
    )

    banner = "=" * 68

    if not is_smtp_configured():
        path = _write_to_outbox(message, to_email)
        print(
            f"\n{banner}\n"
            f"  EMAIL NOT SENT - no SMTP server is configured.\n"
            f"  Verification code for {to_email}: {code}\n"
            f"  Link: {link}\n"
            f"  A copy of the message was saved to: {path}\n"
            f"  To send real email, see EMAIL_SETUP.md\n"
            f"{banner}\n"
        )
        return {"delivered": False, "delivery": "outbox", "detail": str(path)}

    try:
        _send_via_smtp(message)
        print(f"Verification email sent to {to_email} via {settings.SMTP_HOST}.")
        return {"delivered": True, "delivery": "smtp", "detail": settings.SMTP_HOST}
    except Exception as exc:
        # Keep a copy so the code stays recoverable, and say plainly what went
        # wrong instead of leaving the person staring at an empty inbox.
        path = _write_to_outbox(message, to_email)
        reason = f"{type(exc).__name__}: {exc}"
        print(
            f"\n{banner}\n"
            f"  EMAIL DELIVERY FAILED for {to_email}\n"
            f"  Reason: {reason}\n"
            f"  Verification code: {code}\n"
            f"  A copy of the message was saved to: {path}\n"
            f"{banner}\n"
        )
        return {"delivered": False, "delivery": "failed", "detail": reason}
