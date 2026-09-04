import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> int:
    """Read KEY=VALUE lines from a .env file into the environment.

    Every secret this project uses is read from the environment, which is the
    right place for it - but on Windows `set VAR=...` only applies to the one
    console window you typed it in, so a double-clicked start script or a fresh
    terminal silently loses the mail credentials and verification quietly falls
    back to printing codes on screen. A .env file next to main.py survives all
    of that, and .gitignore already excludes it from the repository.

    Hand-rolled rather than pulling in python-dotenv: the format needed here is
    a dozen lines of parsing, and one fewer dependency is one fewer thing that
    can fail to install on the machine this is demonstrated on.

    A real environment variable always wins over the file, so a hosting
    platform's own settings (Render, Hugging Face) are never overridden by a
    stray .env that got deployed alongside the code.
    """
    if not path.is_file():
        return 0

    loaded = 0
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # Quotes are stripped so a password containing spaces or a trailing '#'
        # can be written as SMTP_PASSWORD="abcd efgh ijkl mnop".
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


DOTENV_PATH = BASE_DIR / ".env"
DOTENV_LOADED = _load_dotenv(DOTENV_PATH)

class Settings:
    PROJECT_NAME: str = 'DigiSafe Digital Safety & Record Protection'
    VERSION: str = '1.0.0'
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'digisafe-secret-key-super-secure-knust-2026')
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    
    # 32-byte key for AES-256
    raw_key = os.getenv('DIGISAFE_AES_KEY', 'DigiSafeSecretEncryptionKey2026!')
    if len(raw_key.encode('utf-8')) >= 32:
        AES_KEY: bytes = raw_key.encode('utf-8')[:32]
    else:
        AES_KEY: bytes = raw_key.encode('utf-8').ljust(32, b'#')
        
    DATABASE_URL: str = os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR}/digisafe.db')

    # Demonstration data is OFF by default.
    #
    # This is a real platform, not a showcase: a deployed instance starts with an
    # empty database and fills up with people who actually register. Seeding it
    # with invented complainants and fabricated harassment cases would mean a
    # visitor's first view of an evidence system is fictional records, and the
    # one-click role logins would hand any visitor an administrator session.
    #
    # Set DIGISAFE_SEED_DEMO=true locally when you want the sample cases back
    # for a walkthrough.
    SEED_DEMO_DATA: bool = os.getenv('DIGISAFE_SEED_DEMO', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
    
    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------
    #
    # Nothing here is committed. Every credential is read from the environment,
    # so the repository can be cloned, shared or submitted without carrying a
    # working mailbox password inside it. See EMAIL_SETUP.md for how to fill
    # these in.
    #
    # With no SMTP host configured the platform still works end to end: the
    # verification email is written to storage/outbox/ and printed to the
    # server console instead of being sent. That keeps the flow testable
    # offline - in an exam room with no internet, for instance - without
    # pretending a message was delivered when it was not.
    SMTP_HOST: str = os.getenv('SMTP_HOST', '').strip()
    SMTP_PORT: int = int(os.getenv('SMTP_PORT', '587') or 587)
    SMTP_USER: str = os.getenv('SMTP_USER', '').strip()
    SMTP_PASSWORD: str = os.getenv('SMTP_PASSWORD', '')
    SMTP_STARTTLS: bool = os.getenv('SMTP_STARTTLS', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
    SMTP_SSL: bool = os.getenv('SMTP_SSL', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
    SMTP_TIMEOUT: int = int(os.getenv('SMTP_TIMEOUT', '20') or 20)

    # Verify mail servers against the operating system's certificate store
    # rather than Python's bundled one. On by default because antivirus mail
    # shields (Avast, ESET, Kaspersky) and campus proxies re-sign SMTP
    # connections with a CA the OS trusts and Python does not, which otherwise
    # stops mail leaving the machine entirely. See build_ssl_context() in
    # services/email_service.py for the trade-off; set false to refuse any
    # intercepted connection.
    USE_SYSTEM_TRUST_STORE: bool = os.getenv(
        'DIGISAFE_SYSTEM_TRUST', 'true'
    ).strip().lower() in ('1', 'true', 'yes', 'on')

    MAIL_FROM: str = os.getenv('MAIL_FROM', '').strip() or os.getenv('SMTP_USER', '').strip() or 'no-reply@digisafe.local'
    MAIL_FROM_NAME: str = os.getenv('MAIL_FROM_NAME', 'DigiSafe').strip()

    # Base address used to build the click-through link inside the email.
    #
    # Left UNSET by default, and that is deliberate. A Cloudflare tunnel hands
    # out a different https://....trycloudflare.com host on every restart, and a
    # phone on the same Wi-Fi reaches the laptop by its LAN address, not by
    # 127.0.0.1. Hard-coding either would email people a link to a machine they
    # cannot reach. Unset, the link is built from the address the browser
    # actually used to reach the server, so it is correct wherever the site is
    # being served from.
    #
    # Set it explicitly on a fixed deployment (Render, a real domain). Doing so
    # also pins it: the request's own Host header is then ignored, which closes
    # the host-header injection route where a forged Host would put an attacker's
    # domain into the link.
    APP_BASE_URL: str = os.getenv('APP_BASE_URL', '').strip().rstrip('/')
    # A safety net for the link when no request context is available (a code
    # issued from a script or a test rather than from a browser).
    FALLBACK_BASE_URL: str = 'http://127.0.0.1:8000'

    # Verification can be switched off for a purely offline walkthrough, but it
    # is ON by default: an unverified account is an unowned account.
    REQUIRE_EMAIL_VERIFICATION: bool = os.getenv(
        'DIGISAFE_REQUIRE_VERIFICATION', 'true'
    ).strip().lower() in ('1', 'true', 'yes', 'on')

    VERIFICATION_CODE_TTL_MINUTES: int = int(os.getenv('VERIFICATION_TTL_MINUTES', '30') or 30)
    # Guards a resend button held down, and a mailbox being used as a relay.
    VERIFICATION_RESEND_COOLDOWN_SECONDS: int = int(os.getenv('VERIFICATION_RESEND_COOLDOWN', '60') or 60)
    # A six-digit code is 1-in-a-million per guess; capping the attempts stops
    # an attacker simply working through the million.
    VERIFICATION_MAX_ATTEMPTS: int = int(os.getenv('VERIFICATION_MAX_ATTEMPTS', '8') or 8)

    UPLOAD_DIR: Path = BASE_DIR / 'storage' / 'evidence_files'
    REPORTS_DIR: Path = BASE_DIR / 'storage' / 'reports'
    
settings = Settings()
settings.OUTBOX_DIR = BASE_DIR / 'storage' / 'outbox'


def _writable_dir(preferred: Path) -> Path:
    """Return `preferred` if we can write to it, otherwise a temp directory.

    Serverless platforms ship the application to a READ-ONLY filesystem - on
    Vercel everything under /var/task - with only the system temp directory
    writable. Creating these directories at import time therefore raised
    OSError before a single request was served, and the deployment failed with
    a stack trace pointing at configuration rather than at the real cause.

    Falling back keeps the platform working there. What lands in the fallback
    is only ever regenerable: PDF reports are rebuilt from the record on
    demand, and the outbox holds copies of mail that could not be sent. The
    things that must survive - accounts, evidence, attachments - live in the
    database precisely because no disk here can be trusted to persist.
    """
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / '.write-probe'
        probe.write_bytes(b'')
        probe.unlink()
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / 'digisafe' / preferred.name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


settings.UPLOAD_DIR = _writable_dir(settings.UPLOAD_DIR)
settings.REPORTS_DIR = _writable_dir(settings.REPORTS_DIR)
settings.OUTBOX_DIR = _writable_dir(settings.OUTBOX_DIR)
