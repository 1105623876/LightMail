from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import DB_PATH


@dataclass
class Account:
    email: str
    auth_code: str
    smtp_host: str
    smtp_port: int
    pop3_host: str
    pop3_port: int
    use_ssl: bool = True


@dataclass
class MessageSummary:
    id: int
    account_email: str
    pop3_number: int
    subject: str
    sender: str
    recipient: str
    sent_at: str
    body: str
    raw_content: str
    uidl: str
    is_deleted: bool
    cached_at: str


@dataclass
class ProtocolLog:
    id: int
    account_email: str
    action: str
    content: str
    created_at: str


class MailStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    email TEXT PRIMARY KEY,
                    auth_code TEXT NOT NULL,
                    smtp_host TEXT NOT NULL,
                    smtp_port INTEGER NOT NULL,
                    pop3_host TEXT NOT NULL,
                    pop3_port INTEGER NOT NULL,
                    use_ssl INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_email TEXT NOT NULL,
                    pop3_number INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    body TEXT NOT NULL,
                    raw_content TEXT NOT NULL,
                    uidl TEXT NOT NULL DEFAULT '',
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    cached_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "messages", "uidl", "TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_account_uidl
                ON messages(account_email, uidl)
                WHERE uidl != ''
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS protocol_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_email TEXT NOT NULL,
                    action TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def save_account(self, account: Account) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO accounts (
                    email, auth_code, smtp_host, smtp_port, pop3_host,
                    pop3_port, use_ssl, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    auth_code = excluded.auth_code,
                    smtp_host = excluded.smtp_host,
                    smtp_port = excluded.smtp_port,
                    pop3_host = excluded.pop3_host,
                    pop3_port = excluded.pop3_port,
                    use_ssl = excluded.use_ssl,
                    updated_at = excluded.updated_at
                """,
                (
                    account.email,
                    account.auth_code,
                    account.smtp_host,
                    account.smtp_port,
                    account.pop3_host,
                    account.pop3_port,
                    int(account.use_ssl),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def get_account(self, email: str) -> Account | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
        return self._row_to_account(row) if row else None

    def get_last_account(self) -> Account | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM accounts ORDER BY updated_at DESC LIMIT 1").fetchone()
        return self._row_to_account(row) if row else None

    def cache_messages(self, account_email: str, messages: Iterable[dict[str, str | int]]) -> int:
        cached = 0
        with self.connect() as conn:
            for message in messages:
                pop3_number = int(message["pop3_number"])
                subject = str(message.get("subject", ""))
                sender = str(message.get("sender", ""))
                recipient = str(message.get("recipient", ""))
                sent_at = str(message.get("sent_at", ""))
                body = str(message.get("body", ""))
                raw_content = str(message.get("raw_content", ""))
                uidl = str(message.get("uidl", ""))
                cached_at = datetime.now().isoformat(timespec="seconds")
                existing = conn.execute(
                    """
                    SELECT id FROM messages
                    WHERE account_email = ? AND (uidl = ? OR (uidl = '' AND raw_content = ?))
                    ORDER BY id
                    LIMIT 1
                    """,
                    (account_email, uidl, raw_content),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        DELETE FROM messages
                        WHERE account_email = ? AND id != ? AND uidl = '' AND raw_content = ?
                        """,
                        (account_email, existing["id"], raw_content),
                    )
                    cursor = conn.execute(
                        """
                        UPDATE messages SET
                            pop3_number = ?, subject = ?, sender = ?, recipient = ?,
                            sent_at = ?, body = ?, raw_content = ?, uidl = ?,
                            is_deleted = 0, cached_at = ?
                        WHERE id = ?
                        """,
                        (
                            pop3_number,
                            subject,
                            sender,
                            recipient,
                            sent_at,
                            body,
                            raw_content,
                            uidl,
                            cached_at,
                            existing["id"],
                        ),
                    )
                    cached += cursor.rowcount
                    continue
                cursor = conn.execute(
                    """
                    INSERT INTO messages (
                        account_email, pop3_number, subject, sender, recipient,
                        sent_at, body, raw_content, uidl, cached_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_email,
                        pop3_number,
                        subject,
                        sender,
                        recipient,
                        sent_at,
                        body,
                        raw_content,
                        uidl,
                        cached_at,
                    ),
                )
                cached += cursor.rowcount
        return cached

    def list_messages(self, account_email: str) -> list[MessageSummary]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE account_email = ? AND is_deleted = 0
                ORDER BY pop3_number DESC, id DESC
                """,
                (account_email,),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def get_message(self, message_id: int) -> MessageSummary | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return self._row_to_message(row) if row else None

    def update_message_parse(self, message_id: int, parsed: dict[str, str]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE messages SET
                    subject = ?, sender = ?, recipient = ?, sent_at = ?, body = ?
                WHERE id = ?
                """,
                (
                    parsed.get("subject", ""),
                    parsed.get("sender", ""),
                    parsed.get("recipient", ""),
                    parsed.get("sent_at", ""),
                    parsed.get("body", ""),
                    message_id,
                ),
            )

    def clear_messages(self, account_email: str) -> int:
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM messages WHERE account_email = ?", (account_email,))
            return cursor.rowcount

    def mark_deleted(self, message_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE messages SET is_deleted = 1 WHERE id = ?", (message_id,))

    def add_protocol_log(self, account_email: str, action: str, lines: Iterable[str]) -> None:
        content = "\n".join(lines)
        if not content:
            return
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO protocol_logs (account_email, action, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (account_email, action, content, datetime.now().isoformat(timespec="seconds")),
            )

    def list_protocol_logs(self, account_email: str, limit: int = 20) -> list[ProtocolLog]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM protocol_logs
                WHERE account_email = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (account_email, limit),
            ).fetchall()
        return [self._row_to_protocol_log(row) for row in rows]

    def _row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            email=row["email"],
            auth_code=row["auth_code"],
            smtp_host=row["smtp_host"],
            smtp_port=row["smtp_port"],
            pop3_host=row["pop3_host"],
            pop3_port=row["pop3_port"],
            use_ssl=bool(row["use_ssl"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> MessageSummary:
        return MessageSummary(
            id=row["id"],
            account_email=row["account_email"],
            pop3_number=row["pop3_number"],
            subject=row["subject"],
            sender=row["sender"],
            recipient=row["recipient"],
            sent_at=row["sent_at"],
            body=row["body"],
            raw_content=row["raw_content"],
            uidl=row["uidl"],
            is_deleted=bool(row["is_deleted"]),
            cached_at=row["cached_at"],
        )

    def _row_to_protocol_log(self, row: sqlite3.Row) -> ProtocolLog:
        return ProtocolLog(
            id=row["id"],
            account_email=row["account_email"],
            action=row["action"],
            content=row["content"],
            created_at=row["created_at"],
        )
