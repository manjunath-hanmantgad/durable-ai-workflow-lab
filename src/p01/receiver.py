"""SQLite mock ticket vendor that closes the write/ack gap with idempotency."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from p01.contracts import Command, ContractError, Ticket, canonical_digest


class ConflictError(ContractError):
    """Raised when a key is reused with a different payload."""


class MockReceiver:
    """In-process mock external receiver.

    Uses SQLite with a UNIQUE constraint on command_key. The database,
    not Python locking, decides races. The same key with the same payload
    returns the original ticket; the same key with a different payload
    conflicts.
    """

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._local = threading.local()
        self._ensure_schema()

    @contextmanager
    def _connection(self):
        conn = getattr(self._local, "conn", None)
        own = conn is None
        if own:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        try:
            yield conn
        finally:
            if own:
                conn.close()
                self._local.conn = None

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    command_key TEXT PRIMARY KEY,
                    payload_digest TEXT NOT NULL,
                    ticket_id TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create_ticket(self, command: Command) -> Ticket:
        """Idempotently create one ticket for a stable command key.

        Simulates the external write/ack gap: the caller may retry after
        a dropped response, and the receiver must not duplicate the write.
        """
        digest = command.payload_digest()
        ticket_id = f"TICKET-{digest[:16]}"
        result = {"ticket_id": ticket_id, "command_key": command.key}
        result_json = json.dumps(result, sort_keys=True)

        with self._connection() as conn:
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO tickets (command_key, payload_digest, ticket_id, result_json)
                        VALUES (?, ?, ?, ?)
                        """,
                        (command.key, digest, ticket_id, result_json),
                    )
                return Ticket(
                    ticket_id=ticket_id,
                    command_key=command.key,
                    payload_digest=digest,
                )
            except sqlite3.IntegrityError:
                pass

            # Key exists: return original only if the payload matches.
            row = conn.execute(
                "SELECT payload_digest, ticket_id FROM tickets WHERE command_key = ?",
                (command.key,),
            ).fetchone()

            if row is None:
                raise RuntimeError("unique constraint failed but row missing")

            stored_digest, stored_ticket_id = row
            if stored_digest != digest:
                raise ConflictError(
                    f"key {command.key!r} exists with different payload"
                )

            return Ticket(
                ticket_id=stored_ticket_id,
                command_key=command.key,
                payload_digest=stored_digest,
            )

    def count_tickets(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
            return row[0] if row else 0
