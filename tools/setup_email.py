"""Set up real email delivery, interactively.

    python tools/setup_email.py

Asks for your mail settings, writes them to .env, and immediately sends a test
message so you know whether it worked before anyone is relying on it.

Your password is typed here, into your own terminal, and goes straight into
.env on this machine. It is never echoed to the screen, never printed back, and
.env is excluded by .gitignore so it cannot be committed.
"""

import getpass
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

ENV_PATH = BASE_DIR / ".env"
LINE = "=" * 68

# host, port, starttls, ssl - keyed by the menu number shown to the user.
PROVIDERS = {
    "1": ("Gmail", "smtp.gmail.com", 587, True, False),
    "2": ("Outlook / Hotmail", "smtp-mail.outlook.com", 587, True, False),
    "3": ("Yahoo Mail", "smtp.mail.yahoo.com", 465, False, True),
    "4": ("Brevo (Sendinblue)", "smtp-relay.brevo.com", 587, True, False),
}

GMAIL_HELP = """
  Gmail will NOT accept your normal Google password from an application.
  You need a 16-character App Password:

    1. Switch on 2-Step Verification
       https://myaccount.google.com/security
    2. Create an App Password, name it DigiSafe
       https://myaccount.google.com/apppasswords
    3. Copy the 16 characters it shows you (it is shown only once)

  Paste it below. Spaces are fine - they are stripped automatically.
"""


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


def ask_secret(prompt: str) -> str:
    """Read a password without echoing it, where that is possible.

    getpass reads from the terminal device directly, which is what keeps the
    password off the screen - but it also means it blocks forever when there is
    no terminal, such as input piped in from a script or some embedded consoles.
    Rather than hang, fall back to a visible prompt and say plainly that it will
    be visible, so the choice to continue is the user's.
    """
    if sys.stdin.isatty():
        try:
            return getpass.getpass(f"  {prompt}: ")
        except Exception:
            pass
    print("  (This terminal cannot hide input - what you type WILL be visible.)")
    return input(f"  {prompt}: ")


def write_env(values: dict) -> None:
    """Write .env, preserving any settings already in it.

    Someone may already have set DIGISAFE_AES_KEY or SECRET_KEY here. Rewriting
    the file from scratch would silently drop them - and dropping the AES key
    means every evidence record already stored becomes undecryptable.
    """
    existing = {}
    order = []
    if ENV_PATH.is_file():
        backup = ENV_PATH.with_suffix(f".env.backup-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(ENV_PATH, backup)
        print(f"\n  Existing .env backed up to {backup.name}")
        for raw in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.partition("=")[0].strip()
            if key and key not in existing:
                existing[key] = raw
                order.append(key)

    lines = [
        "# DigiSafe configuration - written by tools/setup_email.py",
        f"# {datetime.now():%Y-%m-%d %H:%M}",
        "#",
        "# This file holds a real password. It is excluded by .gitignore and must",
        "# never be committed, emailed, or screenshotted.",
        "",
        "# --- Email delivery ---",
    ]
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_STARTTLS", "SMTP_SSL",
                "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM", "MAIL_FROM_NAME"):
        value = values[key]
        # Quote the password so spaces in an App Password survive intact.
        if key == "SMTP_PASSWORD":
            value = f'"{value}"'
        lines.append(f"{key}={value}")

    kept = [k for k in order if k not in values]
    if kept:
        lines += ["", "# --- Settings kept from your previous .env ---"]
        lines += [existing[k] for k in kept]

    lines.append("")
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print(LINE)
    print("  DigiSafe - set up real email delivery")
    print(LINE)
    print()
    print("  Right now verification codes are printed in the server console.")
    print("  That works for you, but someone signing up on their own phone")
    print("  cannot see your console, so their account can never be activated.")
    print()
    print("  This sets up one mailbox for DigiSafe to send FROM. After that,")
    print("  anyone can sign up with any address - Gmail, Yahoo, Outlook,")
    print("  @st.knust.edu.gh - and their code arrives in their own inbox.")
    print()
    print(LINE)

    if ENV_PATH.is_file():
        print()
        print(f"  Note: {ENV_PATH.name} already exists. It will be backed up first,")
        print("  and any settings not related to email will be carried over.")

    print()
    print("  Which mail provider are you sending FROM?")
    print()
    for key, (name, host, port, *_rest) in PROVIDERS.items():
        print(f"    {key}. {name:22} ({host}:{port})")
    print("    5. Something else (enter the details yourself)")
    print()

    choice = ask("Choose 1-5", "1")

    if choice in PROVIDERS:
        name, host, port, starttls, use_ssl = PROVIDERS[choice]
    elif choice == "5":
        name = "Custom"
        host = ask("SMTP host (e.g. smtp.yourprovider.com)")
        if not host:
            print("\n  No host given - nothing was changed.")
            return 2
        port = int(ask("SMTP port", "587") or 587)
        use_ssl = port == 465
        starttls = not use_ssl
    else:
        print("\n  Not one of the options - nothing was changed.")
        return 2

    print()
    print(f"  Using {name}: {host}:{port}")

    if choice == "1":
        print(GMAIL_HELP)

    print()
    user = ask("The full email address you are sending FROM")
    if "@" not in user:
        print("\n  That does not look like an email address - nothing was changed.")
        return 2

    print()
    if choice == "1":
        print("  Now the 16-character App Password (NOT your Google password).")
    if sys.stdin.isatty():
        print("  Nothing appears as you type - that is deliberate. Paste and press Enter.")
    password = ask_secret("Password")
    # Google displays App Passwords in four groups of four; people paste them
    # exactly as shown, and the spaces are not part of the credential.
    password = password.replace(" ", "").strip()
    if not password:
        print("\n  No password given - nothing was changed.")
        return 2
    print(f"  Received {len(password)} characters.")
    if choice == "1" and len(password) != 16:
        print()
        print("  WARNING: Gmail App Passwords are exactly 16 characters.")
        print(f"  You entered {len(password)}. If the test below fails, this is why.")

    print()
    display_name = ask("Name recipients should see in the From line", "DigiSafe")

    values = {
        "SMTP_HOST": host,
        "SMTP_PORT": str(port),
        "SMTP_STARTTLS": "true" if starttls else "false",
        "SMTP_SSL": "true" if use_ssl else "false",
        "SMTP_USER": user,
        "SMTP_PASSWORD": password,
        "MAIL_FROM": user,
        "MAIL_FROM_NAME": display_name,
    }

    write_env(values)
    print()
    print(f"  Saved to {ENV_PATH}")
    print("  (.gitignore already excludes it, so it will not be committed.)")

    print()
    print(LINE)
    test_to = ask("Send a test email to which address? (blank to skip)", user)
    if not test_to or "@" not in test_to:
        print()
        print("  Skipped. Test it later with:")
        print("      python tools/check_email.py your.address@example.com")
        print(LINE)
        return 0

    print()
    print(f"  Sending a test message to {test_to} ...")

    # Imported only now, and with the values pushed into the environment first,
    # so this reflects the settings just chosen rather than whatever was loaded
    # when the process started.
    os.environ.update(values)
    from services import email_service  # noqa: E402

    result = email_service.send_verification_email(
        to_email=test_to,
        full_name="DigiSafe Test",
        code=email_service.generate_verification_code(),
        token=email_service.generate_verification_token(),
    )

    print()
    print(LINE)
    if result["delivered"]:
        print("  SUCCESS - the message was accepted for delivery.")
        print()
        print(f"  Open {test_to} and confirm it arrived.")
        print("  If it is not there in a minute, check the SPAM folder - and if")
        print("  that is where it landed, mark it 'not spam' now, so the codes")
        print("  your users receive go to their inbox.")
        print()
        print("  Restart the server and it will say:")
        print(f"      Email verification ON - codes will be sent via {host}")
        print(LINE)
        return 0

    print("  FAILED - nothing was delivered.")
    print()
    print(f"  {result['detail']}")
    print()
    print("  .env has been written, so you can correct one value and retry with:")
    print("      python tools/check_email.py " + test_to)
    print("  check_email.py explains what each error means.")
    print(LINE)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Cancelled - nothing was changed.")
        raise SystemExit(130)
