import json
import sqlite3
from datetime import datetime
from email_classifier import classifier_chain  # The LangChain chain defined earlier

DB_PATH = "inbox_cache.db"


def ensure_classification_columns(cursor: sqlite3.Cursor):
    """Adds classification columns to the emails table if they don't already exist."""
    new_columns = [
        ("category", "TEXT"),
        ("urgency", "TEXT"),
        ("confidence", "REAL"),
        ("action_items", "TEXT"),  # Stored as JSON string
        ("reasoning", "TEXT"),
        ("classified_at", "TIMESTAMP"),
    ]
    
    # Get existing table columns
    cursor.execute("PRAGMA table_info(emails)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE emails ADD COLUMN {col_name} {col_type}")


def process_unclassified_batch(batch_size: int = 10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Ensure columns exist
    ensure_classification_columns(cursor)
    conn.commit()

    # 2. Grab only unclassified emails
    cursor.execute("""
        SELECT message_id, sender, subject, body 
        FROM emails 
        WHERE category IS NULL 
        ORDER BY rowid ASC 
        LIMIT ?
    """, (batch_size,))
    
    emails_to_test = cursor.fetchall()

    if not emails_to_test:
        print("[*] No unclassified emails found. Inbox cache is up to date.")
        conn.close()
        return

    print(f"[*] Found {len(emails_to_test)} unclassified emails. Running classification...\n")

    # 3. Classify and write back to SQLite
    for msg_id, sender, subject, body in emails_to_test:
        # Fallback for empty body and truncate long strings to manage context window
        clean_body = (body or "")[:2500]

        try:
            result = classifier_chain.invoke({
                "sender": sender or "Unknown",
                "subject": subject or "No Subject",
                "body": clean_body,
            })

            # Update row in database
            cursor.execute("""
                UPDATE emails 
                SET category = ?,
                    urgency = ?,
                    confidence = ?,
                    action_items = ?,
                    reasoning = ?,
                    classified_at = ?
                WHERE message_id = ?
            """, (
                result.category,
                result.urgency,
                result.confidence,
                json.dumps(result.action_items),
                result.reasoning,
                datetime.utcnow().isoformat(),
                msg_id
            ))
            conn.commit()

            print(f"[{result.category} | {result.urgency}] {subject[:50]}")
            if result.action_items:
                print(f"  └─ Actions: {result.action_items}")

        except Exception as e:
            print(f"[!] Failed to classify message {msg_id}: {e}")

    conn.close()
    print(f"\n[+] Batch completed and saved.")


if __name__ == "__main__":
    process_unclassified_batch(batch_size=10)
