import base64
import os
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Safe, read-only scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DB_PATH = "inbox_cache.db"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def init_db(db_path: str = DB_PATH):
    """Initialize the local SQLite cache table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT,
            sender TEXT,
            recipient TEXT,
            date TEXT,
            subject TEXT,
            body TEXT,
            raw_snippet TEXT,
            list_unsubscribe TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def authenticate_gmail():
    """Handle OAuth2 flow and return an authenticated Gmail service client."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found. Download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def decode_body_part(part_data: str) -> str:
    """Safely decode base64url encoded MIME strings."""
    try:
        return base64.urlsafe_b64decode(part_data).decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_body(payload: dict) -> str:
    """
    Recursively extract readable body text from nested multipart MIME structures.
    Prefers text/plain; falls back to text/html stripped via BeautifulSoup.
    """
    plain_text = []
    html_text = []

    def walk_parts(parts):
        for part in parts:
            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")
            
            if body_data:
                decoded = decode_body_part(body_data)
                if mime_type == "text/plain":
                    plain_text.append(decoded)
                elif mime_type == "text/html":
                    html_text.append(decoded)
            
            # Recurse into nested multipart containers
            if "parts" in part:
                walk_parts(part["parts"])

    if "parts" in payload:
        walk_parts(payload["parts"])
    else:
        # Single-part message
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            decoded = decode_body_part(body_data)
            if payload.get("mimeType") == "text/html":
                html_text.append(decoded)
            else:
                plain_text.append(decoded)

    # Return plain text if present, otherwise clean HTML
    if plain_text:
        return "\n".join(plain_text).strip()
    if html_text:
        soup = BeautifulSoup("\n".join(html_text), "html.parser")
        # Strip script, style, and tracking pixel blocks
        for element in soup(["script", "style", "noscript", "svg"]):
            element.extract()
        return soup.get_text(separator="\n", strip=True)

    return ""


def fetch_and_cache_emails(service, max_emails: int = 100, query: str = ""):
    """
    Fetch messages matching query (default all) and persist to SQLite.
    Pass query='newer_than:30d' or query='label:INBOX' to restrict if desired.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"[*] Querying messages with query: '{query}'...")
    messages = []
    next_page_token = None

    while True:
        results = service.users().messages().list(
            userId="me",
            q=query,
            pageToken=next_page_token,
            maxResults=min(100, max_emails - len(messages))
        ).execute()

        batch = results.get("messages", [])
        if not batch:
            break

        messages.extend(batch)
        print(f"[*] Retrieved {len(messages)} message IDs so far...")

        if len(messages) >= max_emails:
            break

        next_page_token = results.get("nextPageToken")
        if not next_page_token:
            break

    print(f"[*] Total message headers indexed: {len(messages)}. Fetching full message payloads...")

    saved_count = 0
    for idx, msg_meta in enumerate(messages, 1):
        msg_id = msg_meta["id"]

        # Check if already present in cache to avoid duplicate payload fetches
        cursor.execute("SELECT 1 FROM emails WHERE message_id = ?", (msg_id,))
        if cursor.fetchone():
            continue

        try:
            full_msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()

            payload = full_msg.get("payload", {})
            headers = {
                h["name"].lower(): h["value"]
                for h in payload.get("headers", [])
            }

            sender = headers.get("from", "")
            recipient = headers.get("to", "")
            date_str = headers.get("date", "")
            subject = headers.get("subject", "")
            list_unsubscribe = headers.get("list-unsubscribe", "")
            thread_id = full_msg.get("threadId", "")
            snippet = full_msg.get("snippet", "")
            body = extract_body(payload)

            cursor.execute("""
                INSERT OR IGNORE INTO emails (
                    message_id, thread_id, sender, recipient,
                    date, subject, body, raw_snippet, list_unsubscribe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id, thread_id, sender, recipient,
                date_str, subject, body, snippet, list_unsubscribe
            ))
            
            saved_count += 1
            if saved_count % 10 == 0:
                conn.commit()
                print(f"    -> Parsed and saved {saved_count} new emails...")

        except Exception as e:
            print(f"[!] Error fetching message ID {msg_id}: {e}")

    conn.commit()
    conn.close()
    print(f"\n[+] Done! Cached {saved_count} new emails in '{DB_PATH}'.")


if __name__ == "__main__":
    init_db()
    gmail_service = authenticate_gmail()
    
    # Set max_emails to your target (e.g., 50 for quick initial run, or 500 for full set)
    # Use standard Gmail search filters in query if needed (e.g., 'category:primary' or 'newer_than:90d')
    fetch_and_cache_emails(service=gmail_service, max_emails=100, query="")

