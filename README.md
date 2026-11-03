# email_urgency_classification using LangChain
### Important emails get buried under hundreds and thousands of trivial emails such as advertisements. This project aims to go through each email using an LLM to classify its urgency and action needed.
---
### Google Cloud Setup (One-time):
To download and cache emails locally

    1.  Go to the Google Cloud Console and create/select a project.

    2. Enable the Gmail API.

    3.  Under APIs & Services > Credentials, create an OAuth 2.0 Client ID (Application type: Desktop App).

    4. Download the JSON credential file, rename it to credentials.json, and place it in your working directory.

Run: python fetch_emails.py

### To install Ollama
Run: curl -fsSL https://ollama.com/install.sh | sh

### To start Ollama server
Run: ollama serve

### Verify Python dependencies in your active environment:
pip install langchain-core langchain-ollama pydantic

### Verify that Ollama is serving the model in the background:
- ollama list
### If qwen2.5:3b is missing, pull it:
- ollama pull qwen2.5:3b

### Finally:
Run: python main.py

### results are stored in sqlite3 database
- **REQUIRE_ACTION**: Direct questions, explicit tasks, code review requests, approvals, or operational blockers demanding human intervention.
- **NOTIFICATION**: Automated machine alerts, CI/CD runs, social pings, and status updates not involving billing/finances.
- **ADVERTISEMENT**: Cold sales pitches, promotional marketing blasts, commercial discounts, or event promos.
- **TRANSACTIONAL**: Financial invoices, receipts, order tracking, password resets, or flight/train bookings.
- **NEWSLETTER**: Curated reading material, technical digests, and subscribed industry updates.
- **DIRECT_COMMUNICATION**: Conversational messages or FYI notes from a human that require no response or action.
---
---
### model used: qwen2.5:3b

