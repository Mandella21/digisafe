"""Send one real test email and say precisely what happened.

    python tools/check_email.py you@example.com

Registration is the wrong place to discover that a mail password is wrong: by
then a person is already staring at an inbox that will never receive anything.
This asks the same question directly - "can this machine actually deliver mail
to that address right now?" - and turns the SMTP library's terse errors into
the specific thing to go and fix.

Run it once before a demonstration. If it says DELIVERED, sign-up will work for
every address people put in, on any provider.
"""

import sys
from pathlib import Path

# Importable when run as `python tools/check_email.py` from the project root,
# which is how the instructions tell people to run it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings, DOTENV_PATH, DOTENV_LOADED  # noqa: E402
from services import email_service  # noqa: E402

LINE = "=" * 70


# Each entry maps a fragment of a real SMTP/socket error to what actually needs
# fixing. The fragments are lowercase; the incoming message is lowercased too.
DIAGNOSES = [
    (
        "application-specific password required",
        "Gmail needs an App Password, not your normal Google password.\n"
        "  Create one at https://myaccount.google.com/apppasswords\n"
        "  (2-Step Verification must be ON before that page will work.)",
    ),
    (
        "username and password not accepted",
        "The mailbox rejected these credentials.\n"
        "  On Gmail this almost always means SMTP_PASSWORD is the account\n"
        "  password rather than a 16-character App Password.\n"
        "  Also check SMTP_USER is the full address, including @gmail.com.",
    ),
    (
        "authentication failed",
        "The username or password was refused. Retype SMTP_PASSWORD - a\n"
        "  copy-paste that picked up a trailing space is the usual cause.",
    ),
    (
        "wrong_version_number",
        "Port/encryption mismatch. Port 465 needs SMTP_SSL=true; port 587\n"
        "  needs SMTP_STARTTLS=true. You currently have port "
        f"{settings.SMTP_PORT}.",
    ),
    (
        "getaddrinfo failed",
        f"The hostname '{settings.SMTP_HOST}' could not be resolved.\n"
        "  Check it for typos, and check this machine is online.",
    ),
    (
        "timed out",
        f"No answer from {settings.SMTP_HOST}:{settings.SMTP_PORT}.\n"
        "  A firewall or the campus network is likely blocking outbound SMTP.\n"
        "  Try a phone hotspot, or a provider that offers port 2525.",
    ),
    (
        "connection refused",
        f"{settings.SMTP_HOST} refused the connection on port "
        f"{settings.SMTP_PORT}.\n  Check the port number against your provider's documentation.",
    ),
    (
        "sender address rejected",
        f"The server will not send as '{settings.MAIL_FROM}'.\n"
        "  MAIL_FROM usually has to match SMTP_USER, or be an address the\n"
        "  provider has verified.",
    ),
]


def explain(reason: str) -> str:
    lowered = reason.lower()
    for fragment, advice in DIAGNOSES:
        if fragment in lowered:
            return advice
    return (
        "Not a failure this script recognises. The raw error is above -\n"
        "  search for it, or check EMAIL_SETUP.md."
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        print("Give one address to send the test to, for example:")
        print("    python tools/check_email.py you@example.com")
        return 2

    recipient = sys.argv[1].strip()
    if "@" not in recipient:
        print(f"'{recipient}' does not look like an email address.")
        return 2

    print(LINE)
    print("  DigiSafe email delivery check")
    print(LINE)

    if DOTENV_LOADED:
        print(f"  Config file : {DOTENV_PATH} ({DOTENV_LOADED} setting(s) read)")
    elif DOTENV_PATH.is_file():
        print(f"  Config file : {DOTENV_PATH} (present, but every value was")
        print("                already set in the environment, which wins)")
    else:
        print(f"  Config file : none - no .env found at {DOTENV_PATH}")

    print(f"  SMTP host   : {settings.SMTP_HOST or '(not set)'}")
    print(f"  SMTP port   : {settings.SMTP_PORT}")
    print(f"  SMTP user   : {settings.SMTP_USER or '(not set)'}")
    # Never print the password. Its length and presence are enough to spot the
    # two mistakes that actually happen: an empty value, or a Google App
    # Password pasted with its spaces (16 characters vs 19).
    if settings.SMTP_PASSWORD:
        print(f"  SMTP pass   : set, {len(settings.SMTP_PASSWORD)} characters")
    else:
        print("  SMTP pass   : (not set)")
    print(f"  Encryption  : {'SSL' if settings.SMTP_SSL else 'STARTTLS' if settings.SMTP_STARTTLS else 'NONE'}")
    print(f"  From        : {settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>")
    print(f"  Sending to  : {recipient}")
    print(LINE)

    if not email_service.is_smtp_configured():
        print()
        print("  NOT CONFIGURED - no mail will be sent to anybody.")
        print()
        print("  DigiSafe still runs in this state: verification codes are")
        print("  printed in the server console and saved to storage/outbox/.")
        print("  That is enough to demonstrate the flow, but people signing up")
        print("  on their own phones cannot see your console.")
        print()
        print("  To fix: copy .env.example to .env and fill in SMTP_HOST,")
        print("  SMTP_USER, SMTP_PASSWORD and MAIL_FROM. Step-by-step")
        print("  instructions are in EMAIL_SETUP.md.")
        print(LINE)
        return 1

    print()
    print("  Connecting and sending...")

    code = email_service.generate_verification_code()
    token = email_service.generate_verification_token()
    result = email_service.send_verification_email(
        to_email=recipient,
        full_name="DigiSafe Test",
        code=code,
        token=token,
    )

    print()
    print(LINE)
    if result["delivered"]:
        print("  DELIVERED")
        print()
        print(f"  A verification email was accepted by {result['detail']} for")
        print(f"  delivery to {recipient}.")
        print()
        print("  Open that inbox and confirm it arrived. If it is not there")
        print("  within a minute, check the spam folder - and if that is where")
        print("  it landed, mark it 'not spam' before your demonstration so")
        print("  later messages go to the inbox.")
        print()
        print("  Real sign-up will now work for any address, on any provider.")
        print(LINE)
        return 0

    print("  FAILED - nothing was delivered.")
    print()
    print(f"  Error: {result['detail']}")
    print()
    print("  Most likely cause:")
    print(f"  {explain(result['detail'])}")
    print()
    print(f"  A copy of the message that could not be sent is in storage/outbox/.")
    print("  More detail: EMAIL_SETUP.md")
    print(LINE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
