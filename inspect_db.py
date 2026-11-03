import sqlite3

conn = sqlite3.connect("inbox_cache.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM emails")
total = cursor.fetchone()[0]
print(f"Total Cached Emails: {total}")

cursor.execute("SELECT sender, subject, LENGTH(body) FROM emails ORDER BY rowid DESC LIMIT 5")
print("\nMost Recent 5 Downloads:")
for sender, subject, body_len in cursor.fetchall():
    print(f"- From: {sender[:40]:<40} | Subject: {subject[:45]:<45} | Body Chars: {body_len}")

conn.close()
