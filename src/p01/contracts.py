"""Strict data boundaries and pure identity/state rules, not authorization or durability."""

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


def _uuid_string(value: str) -> str:
    return str(UUID(value))


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("text must contain a non-whitespace character")
    return value


def _utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be UTC-aware")
    return value


UUIDString = Annotated[str, AfterValidator(_uuid_string)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Title = Annotated[str, Field(min_length=1, max_length=160), AfterValidator(_nonblank)]
Text = Annotated[str, Field(min_length=1, max_length=4000), AfterValidator(_nonblank)]
UtcTimestamp = Annotated[AwareDatetime, AfterValidator(_utc)]
Version = Annotated[int, Field(ge=1, le=1)]
AttemptCount = Annotated[int, Field(ge=0, le=3)]
Decision = Literal["approve", "reject"]
Permission = Literal["submit", "approve", "recover"]
ErrorCode = Literal[
    "invalid_output", "unauthorized", "timeout", "retry_exhausted",
    "unsupported_version", "ambiguous_outcome",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Principal(StrictModel):
    """Server-resolved context, never a model-generated grant of permission."""

    tenant_id: UUIDString
    subject_id: UUIDString
    permissions: frozenset[Permission]


class RequestInput(StrictModel):
    text: Text


class TicketDraft(StrictModel):
    title: Title
    body: Text
    priority: Literal["low", "normal", "high"]


class ApprovalInput(StrictModel):
    """An intent selection; actor, authority, and expiry come from trusted records."""

    draft_digest: Digest
    decision: Decision


def canonical_digest(value: dict) -> str:
    """Hash exact JSON content; canonicalize object order, not text or list order."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def command_key(tenant_id: str, workflow_id: str, action_version: int) -> str:
    """Same command identity on every attempt; never include an attempt number."""
    if type(action_version) is not int or action_version != 1:
        raise ValueError("unsupported action version")
    return canonical_digest({
        "tenant_id": _uuid_string(tenant_id),
        "workflow_id": _uuid_string(workflow_id),
        "action_version": action_version,
    })


class ExternalCommand(StrictModel):
    key: Digest
    tenant_id: UUIDString
    workflow_id: UUIDString
    action_version: Version = 1
    draft: TicketDraft

    @model_validator(mode="after")
    def bind_key_to_identity(self) -> "ExternalCommand":
        if self.key != command_key(self.tenant_id, self.workflow_id, self.action_version):
            raise ValueError("command key does not match its identity")
        return self


class TicketResult(StrictModel):
    ticket_id: UUIDString
    command_key: Digest


class RunStatus(StrEnum):
    ACCEPTED = "accepted"
    DRAFTING = "drafting"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ContractError(ValueError):
    def __init__(self, code: Literal["invalid_transition"]):
        self.code = code
        super().__init__(code)


_FORWARD = {
    RunStatus.ACCEPTED: {RunStatus.DRAFTING, RunStatus.FAILED, RunStatus.NEEDS_REVIEW},
    RunStatus.DRAFTING: {RunStatus.AWAITING_APPROVAL, RunStatus.FAILED, RunStatus.NEEDS_REVIEW},
    RunStatus.AWAITING_APPROVAL: {
        RunStatus.EXECUTING, RunStatus.REJECTED, RunStatus.EXPIRED,
        RunStatus.FAILED, RunStatus.NEEDS_REVIEW,
    },
    RunStatus.EXECUTING: {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.NEEDS_REVIEW},
    # Completion requires independently verified reconciliation, never another blind create.
    RunStatus.NEEDS_REVIEW: {RunStatus.COMPLETED},
}


def transition(current: RunStatus, target: RunStatus) -> RunStatus:
    """Structural guard only; the caller must also check authority and state evidence."""
    if not isinstance(current, RunStatus) or not isinstance(target, RunStatus):
        raise ContractError("invalid_transition")
    if current == target or target in _FORWARD.get(current, set()):
        return target
    raise ContractError("invalid_transition")


class WorkflowState(StrictModel):
    """Validated boundary form; serialize to a JSON mapping for a future graph adapter."""

    version: Version = 1
    workflow_id: UUIDString
    tenant_id: UUIDString
    subject_id: UUIDString
    status: RunStatus = RunStatus.ACCEPTED
    draft: TicketDraft | None = None
    draft_digest: Digest | None = None
    approval: ApprovalInput | None = None
    result: TicketResult | None = None
    error_code: ErrorCode | None = None


class RunRecord(StrictModel):
    """Record schema only; transactions, current authorization, and recovery come later."""

    version: Version = 1
    workflow_id: UUIDString
    tenant_id: UUIDString
    subject_id: UUIDString
    request_digest: Digest
    created_at: UtcTimestamp
    updated_at: UtcTimestamp
    expires_at: UtcTimestamp | None = None
    status: RunStatus = RunStatus.ACCEPTED
    draft: TicketDraft | None = None
    draft_digest: Digest | None = None
    decision: Decision | None = None
    decided_by: UUIDString | None = None
    decided_at: UtcTimestamp | None = None
    result: TicketResult | None = None
    model_attempts: AttemptCount = 0
    tool_attempts: AttemptCount = 0
    ambiguous: bool = False
    recovery_requested: bool = False
