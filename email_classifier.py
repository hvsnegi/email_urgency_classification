from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
# Swap ChatOllama with ChatOpenAI if running against OpenAI/cloud endpoints
from langchain_ollama import ChatOllama


# 1. Define the Structured Output Schema
EmailCategory = Literal[
    "REQUIRE_ACTION",
    "NOTIFICATION",
    "ADVERTISEMENT",
    "TRANSACTIONAL",
    "NEWSLETTER",
    "DIRECT_COMMUNICATION",
]

class EmailClassification(BaseModel):
    category: EmailCategory = Field(
        ...,
        description="The primary classification bucket that best fits the email's core purpose."
    )
    urgency: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ...,
        description="Urgency level. HIGH = immediate deadline/critical blocker, MEDIUM = response expected in 24-48h, LOW = FYI/read at leisure."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score for the assigned category from 0.0 to 1.0."
    )
    action_items: List[str] = Field(
        default_factory=list,
        description="Explicit tasks, replies, or decisions expected from the recipient. Empty if none."
    )
    reasoning: str = Field(
        ...,
        description="A 1-2 sentence justification for the classification decision."
    )


# 2. System Instructions & Prompt Template
SYSTEM_PROMPT = """You are an automated email triage classifier. Analyze incoming emails and classify them strictly into one of the following categories:

- **REQUIRE_ACTION**: Direct questions, explicit tasks, code review requests, approvals, or operational blockers demanding human intervention.
- **NOTIFICATION**: Automated machine alerts, CI/CD runs, social pings, and status updates not involving billing/finances.
- **ADVERTISEMENT**: Cold sales pitches, promotional marketing blasts, commercial discounts, or event promos.
- **TRANSACTIONAL**: Financial invoices, receipts, order tracking, password resets, or flight/train bookings.
- **NEWSLETTER**: Curated reading material, technical digests, and subscribed industry updates.
- **DIRECT_COMMUNICATION**: Conversational messages or FYI notes from a human that require no response or action.

Rules:
1. Prioritize intent over sender: If an automated alert requires human action (e.g., 'Payment Failed - Update Card'), categorize as REQUIRE_ACTION.
2. If REQUIRE_ACTION, extract clear, concise bullet points in `action_items`. Otherwise, keep `action_items` empty.
3. Keep `reasoning` brief and factual."""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    (
        "human",
        "Sender: {sender}\nSubject: {subject}\n\nEmail Body:\n{body}"
    ),
])


# 3. Model Initialization & Structured Binding
# Using Qwen 2.5 or Llama 3 via Ollama for local execution; change model name as needed
llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0.0,
)

structured_llm = llm.with_structured_output(EmailClassification)
classifier_chain = prompt | structured_llm


# 4. Helper Function & Demonstration
def classify_email(sender: str, subject: str, body: str) -> EmailClassification:
    return classifier_chain.invoke({
        "sender": sender,
        "subject": subject,
        "body": body,
    })


if __name__ == "__main__":
    sample_emails = [
        {
            "sender": "lead-architect@company.com",
            "subject": "PR #142: Fix Redis cache invalidation bug",
            "body": "Hey, I left comments on the cache eviction logic. Can you review them and push the updated unit tests before 4 PM today so we can cut the release?"
        },
        {
            "sender": "notifications@github.com",
            "subject": "[GitHub] Workflow run 'Build & Lint' passed on main",
            "body": "Run #891 for commit 4a12f9 completed successfully in 1m 24s. All 42 checks passed."
        },
        {
            "sender": "offers@cloudservice.io",
            "subject": "Exclusive 40% discount on dedicated GPU instances",
            "body": "Upgrade your compute cluster this week and save 40% on all A100 GPU reservations. Click here to claim your coupon before Friday midnight."
        },
        {
            "sender": "billing@stripe.com",
            "subject": "Your receipt for AWS Lightsail ($12.50)",
            "body": "Thank you for your payment. Invoice #INV-2026-881 has been paid via Mastercard ending in 4112. You can download the PDF receipt attached."
        }
    ]

    for idx, email in enumerate(sample_emails, 1):
        print(f"\n--- Email {idx}: {email['subject']} ---")
        result = classify_email(
            sender=email["sender"],
            subject=email["subject"],
            body=email["body"]
        )
        print(f"Category:     {result.category}")
        print(f"Urgency:      {result.urgency}")
        print(f"Confidence:   {result.confidence:.2f}")
        print(f"Action Items: {result.action_items}")
        print(f"Reasoning:    {result.reasoning}")
