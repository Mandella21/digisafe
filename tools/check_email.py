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


def probe_connection(host, port, use_ssl, starttls, timeout=12):
    """Open the connection and do the TLS handshake, without logging in.

    Separating "can this machine reach a mail server" from "are these
    credentials right" matters, because the two failures need completely
    different fixes and their error messages look nothing alike. A blocked port
    or an intercepted certificate is not something a different password will
    ever solve, and it is worth knowing before someone goes and generates one.

    Returns (ok, kind, detail) where kind is one of:
      ok           - reached it, certificate valid
      intercepted  - something is re-signing the connection (see below)
      blocked      - no route, refused, or timed out
      tls          - some other TLS problem
      smtp         - reached it, but the server misbehaved
    """
    import smtplib

    from services import email_service

    # The same context the application itself will use, so a probe that passes
    # cannot be followed by a send that fails on trust.
    context = email_service.build_ssl_context()
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            if starttls:
                server.starttls(context=context)
        server.ehlo()
        server.quit()
        return True, "ok", ""
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        lowered = reason.lower()

        # Antivirus "mail shields" and corporate proxies terminate the TLS
        # session and present a certificate signed by their own CA. Some of
        # those certificates are malformed by modern standards - most commonly
        # a CA certificate whose Basic Constraints extension is not marked
        # critical - and OpenSSL refuses them outright. The give-away is that
        # the failure is a certificate error against a host whose real
        # certificate is unimpeachable.
        if "certificate verify failed" in lowered or "certificate_verify" in lowered:
            return False, "intercepted", reason
        if "unable to get local issuer" in lowered:
            return False, "intercepted", reason
        if any(k in lowered for k in ("getaddrinfo", "timed out", "refused", "unreachable", "timeout")):
            return False, "blocked", reason
        if "ssl" in lowered or "tls" in lowered:
            return False, "tls", reason
        return False, "smtp", reason


INTERCEPTION_ADVICE = """\
  Something on this machine or network is intercepting the encrypted
  connection and presenting its own certificate. This is almost always an
  antivirus "mail shield" or a campus/corporate proxy scanning outbound mail.

  No password will fix this - the connection is refused before any password is
  sent. Four ways forward, easiest first:

    1. Install truststore, which lets DigiSafe verify against the operating
       system's certificate store instead of Python's bundled one. Windows
       already trusts the scanner's certificate, so this usually just works:
         pip install truststore

    2. Use a provider that offers port 2525, which these scanners usually
       leave alone. Brevo (free, 300 emails/day) does:
         SMTP_HOST=smtp-relay.brevo.com   SMTP_PORT=2525

    3. Turn off the scanner's encrypted-mail scanning. In Avast:
         Menu > Settings > Protection > Core Shields
         > Mail Shield > untick "Scan secure connections"
       (Other products call it SSL scanning or HTTPS/mail filtering.)

    4. Try a different network - a phone hotspot is the quickest test, and
       rules the network in or out in about a minute.\
"""


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
    try:
        import truststore  # noqa: F401
        trust = "operating system store" if settings.USE_SYSTEM_TRUST_STORE else "Python bundled (system trust disabled)"
    except ImportError:
        trust = "Python bundled (truststore not installed)"
    print(f"  Trust store : {trust}")
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
    print("  Step 1 of 2 - can this machine reach the mail server at all?")
    ok, kind, detail = probe_connection(
        settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_SSL, settings.SMTP_STARTTLS
    )
    if ok:
        print("    Reached it, and the certificate is valid.")
    else:
        print(f"    Could not establish a trusted connection: {detail}")
        print()
        print(LINE)
        if kind == "intercepted":
            print("  CONNECTION INTERCEPTED")
            print()
            print(INTERCEPTION_ADVICE)
        elif kind == "blocked":
            print("  CANNOT REACH THE MAIL SERVER")
            print()
            print(f"  Nothing answered at {settings.SMTP_HOST}:{settings.SMTP_PORT}.")
            print("  Check the host and port, and whether this network allows")
            print("  outbound mail. A phone hotspot is the quickest way to tell.")
        else:
            print("  TLS PROBLEM")
            print()
            print("  Port 465 needs SMTP_SSL=true; port 587 needs SMTP_STARTTLS=true.")
        print(LINE)
        return 1

    print()
    print("  Step 2 of 2 - signing in and sending...")

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
