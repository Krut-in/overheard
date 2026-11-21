"""Read-only Gmail fetch of booking-like mail from the lab inbox, returned as plain text for overheard.ingest."""
import argparse
import base64
import html
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"
CLIENT_FILE = "gmail_client.json"
TOKEN_FILE = "gmail_token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # read-only, nothing else
TERMS = ['"SAMPLE BOOKING"', "confirmation", "booking", "reservation", "itinerary", "e-ticket",
         "confirmee", "bevestiging", "boeking"]
MAX_MESSAGES = 30


def query(since: date | str | None = None) -> str:
    """Gmail search for booking-like mail, newest first; `since` limits it to mail after that day."""
    q = "subject:(" + " OR ".join(TERMS) + ") -in:spam -in:trash"
    if since:
        d = since if isinstance(since, date) else datetime.fromisoformat(str(since)).date()
        q += f" after:{d:%Y/%m/%d}"
    return q


def _creds(creds_dir: Path):
    """Installed-app OAuth flow; the token is cached next to the client file (both gitignored)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    client, token = creds_dir / CLIENT_FILE, creds_dir / TOKEN_FILE
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not client.exists():
            raise FileNotFoundError(f"OAuth client missing: {client} (ticket H1 creates it)")
        creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES).run_local_server(port=0)
    token.write_text(creds.to_json())
    token.chmod(0o600)
    return creds


def _b64(s: str) -> str:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")


def _html_to_text(h: str) -> str:
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", h)
    return re.sub(r"\n\s*\n+", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def body_text(payload: dict) -> str:
    """Walk a Gmail MIME payload: first text/plain part, else text/html stripped to text."""
    plain, rich = [], []

    def walk(p):
        mime, data = p.get("mimeType", ""), p.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_b64(data))
        elif data and mime == "text/html":
            rich.append(_html_to_text(_b64(data)))
        for sub in p.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return (plain or rich or [""])[0].strip()


def fetch_booking_emails(creds_dir=SECRETS, since: date | str | None = None) -> list[str]:
    """Booking-like messages from the signed-in (lab) inbox as 'Subject: ...\\n\\n<body>' strings."""
    from googleapiclient.discovery import build

    svc = build("gmail", "v1", credentials=_creds(Path(creds_dir)), cache_discovery=False)
    res = svc.users().messages().list(userId="me", q=query(since), maxResults=MAX_MESSAGES).execute()
    out = []
    for m in res.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        out.append(f"Subject: {headers.get('subject', '')}\n\n{body_text(msg['payload'])}\n")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print the query and scope, no network")
    ap.add_argument("--fetch", action="store_true", help="run the OAuth flow and list matching mail")
    ap.add_argument("--parse", action="store_true", help="with --fetch: also build the Itinerary with Neon")
    ap.add_argument("--since", default=str(date.today() - timedelta(days=30)))
    ap.add_argument("--creds-dir", default=str(SECRETS))
    a = ap.parse_args()
    if a.dry_run or not a.fetch:
        print("query:", query(a.since))
        print("scope:", SCOPES[0].rsplit("/", 1)[-1], f"({SCOPES[0]})")
        print("client:", Path(a.creds_dir) / CLIENT_FILE, "exists" if (Path(a.creds_dir) / CLIENT_FILE).exists() else "missing")
        return
    mails = fetch_booking_emails(a.creds_dir, a.since)
    print(f"{len(mails)} booking-like messages")
    for m in mails:
        print(" -", m.splitlines()[0][:100])
    if a.parse and mails:
        import json
        from overheard import ingest
        print(json.dumps(ingest.parse(mails, source="gmail"), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
