from __future__ import annotations

import re
from email import policy
from email.header import decode_header
from email.message import EmailMessage
from email.parser import BytesParser, Parser
from email.utils import formataddr, formatdate, parseaddr
from html import unescape


def build_message(sender: str, recipient: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["From"] = formataddr((sender, sender))
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message.set_content(body, subtype="plain", charset="utf-8")
    return message.as_string(policy=policy.SMTP)


def parse_message(raw_content: str | bytes) -> dict[str, str]:
    if isinstance(raw_content, bytes):
        message = BytesParser(policy=policy.default).parsebytes(raw_content)
        raw_text = raw_content.decode("utf-8", errors="replace")
    else:
        message = Parser(policy=policy.default).parsestr(raw_content)
        raw_text = raw_content

    return {
        "subject": decode_mime_header(message.get("Subject", "")),
        "sender": decode_address(message.get("From", "")),
        "recipient": decode_address(message.get("To", "")),
        "sent_at": message.get("Date", ""),
        "body": normalize_display_text(extract_text_body(message)),
        "raw_content": raw_text,
    }


def decode_mime_header(value: str) -> str:
    parts: list[str] = []
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def decode_address(value: str) -> str:
    name, address = parseaddr(value)
    decoded_name = decode_mime_header(name)
    return f"{decoded_name} <{address}>" if decoded_name else address


def extract_text_body(message) -> str:
    if message.is_multipart():
        html_body = ""
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                return part.get_content()
            if part.get_content_type() == "text/html" and not html_body:
                html_body = part.get_content()
        return html_to_text(html_body) if html_body else ""
    if message.get_content_type() == "text/html":
        return html_to_text(message.get_content())
    if message.get_content_maintype() == "text":
        return message.get_content()
    return ""


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</?(p|div|tr|li|table|h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return normalize_display_text(unescape(text))


def normalize_display_text(text: str) -> str:
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
