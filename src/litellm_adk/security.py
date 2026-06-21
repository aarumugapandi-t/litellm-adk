import re
from typing import Dict, Any, List

class PIIScrubber:
    """
    Production-ready PII Scrubber to mask sensitive information before sending prompts to external providers.
    Uses regex patterns to identify and mask SSNs, Credit Cards, and Emails.
    """
    
    PATTERNS = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    }

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Masks PII in a single string."""
        if not isinstance(text, str):
            return text
            
        scrubbed = text
        for pii_type, pattern in cls.PATTERNS.items():
            scrubbed = re.sub(pattern, f"[{pii_type}_REDACTED]", scrubbed)
        return scrubbed

    @classmethod
    def scrub_messages(cls, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deep copy and mask PII across a list of LLM messages."""
        scrubbed_messages = []
        for msg in messages:
            scrubbed_msg = msg.copy()
            if "content" in scrubbed_msg and isinstance(scrubbed_msg["content"], str):
                scrubbed_msg["content"] = cls.scrub_text(scrubbed_msg["content"])
            scrubbed_messages.append(scrubbed_msg)
        return scrubbed_messages
