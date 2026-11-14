"""Minimal data rules for the write/ack-gap proof."""

import hashlib
import json
from dataclasses import dataclass


class ContractError(Exception):
    """A domain rule violation, not a programming bug."""


@dataclass(frozen=True)
class Command:
    """One intent to create an external ticket.

    The key must be stable across retries of the same intent.
    The digest captures the payload so a changed intent cannot
    silently reuse an old key.
    """

    key: str
    payload: dict

    def payload_digest(self) -> str:
        return canonical_digest(self.payload)


@dataclass(frozen=True)
class Ticket:
    """The stored result of one successful receiver write."""

    ticket_id: str
    command_key: str
    payload_digest: str


def canonical_digest(value: dict) -> str:
    """Stable, deterministic digest for JSON-serializable data."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
