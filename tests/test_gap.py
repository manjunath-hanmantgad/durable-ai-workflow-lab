"""Proof of the write/ack gap and receiver-side idempotency."""

import threading
from pathlib import Path

import pytest

from p01.contracts import Command, canonical_digest
from p01.receiver import ConflictError, MockReceiver


def test_lost_ack_retry_returns_same_ticket(tmp_path: Path) -> None:
    """A retry after a dropped response must not create a duplicate."""
    receiver = MockReceiver(tmp_path / "tickets.db")
    command = Command(key="req-1", payload={"title": "Fix login", "priority": "high"})

    first = receiver.create_ticket(command)
    second = receiver.create_ticket(command)

    assert first.ticket_id == second.ticket_id
    assert receiver.count_tickets() == 1


def test_concurrent_duplicates_create_one_ticket(tmp_path: Path) -> None:
    """Database uniqueness, not Python locking, suppresses duplicate writes."""
    db_path = tmp_path / "tickets.db"
    command = Command(key="concurrent-1", payload={"title": "Concurrent"})
    results: list[str] = []
    errors: list[Exception] = []

    def attempt() -> None:
        try:
            receiver = MockReceiver(db_path)
            ticket = receiver.create_ticket(command)
            results.append(ticket.ticket_id)
        except Exception as exc:  # pragma: no cover - failures are bugs
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(set(results)) == 1
    assert MockReceiver(db_path).count_tickets() == 1


def test_changed_payload_conflicts(tmp_path: Path) -> None:
    """Reusing a key with different intent is a conflict, not an update."""
    receiver = MockReceiver(tmp_path / "tickets.db")
    key = " mutable-1"
    original = Command(key=key, payload={"title": "Original"})
    changed = Command(key=key, payload={"title": "Changed"})

    receiver.create_ticket(original)

    with pytest.raises(ConflictError):
        receiver.create_ticket(changed)

    assert receiver.count_tickets() == 1


def test_survives_receiver_restart(tmp_path: Path) -> None:
    """The stored result must outlive the process that wrote it."""
    db_path = tmp_path / "tickets.db"
    command = Command(key="survive-1", payload={"title": "Survive restart"})

    before = MockReceiver(db_path).create_ticket(command)
    after = MockReceiver(db_path).create_ticket(command)

    assert before.ticket_id == after.ticket_id
    assert MockReceiver(db_path).count_tickets() == 1


def test_command_digest_is_stable_and_payload_sensitive() -> None:
    """Canonical digest ignores key order but detects value changes."""
    a = Command("k", {"title": "A", "priority": "high"})
    b = Command("k", {"priority": "high", "title": "A"})
    c = Command("k", {"title": "B", "priority": "high"})

    assert a.payload_digest() == b.payload_digest()
    assert a.payload_digest() != c.payload_digest()
