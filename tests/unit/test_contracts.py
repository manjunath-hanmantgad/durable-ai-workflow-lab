"""Pure boundary tests: no model, database, HTTP client, or test doubles."""

from datetime import UTC, datetime, timedelta, timezone
from importlib import import_module

import pytest
from pydantic import ValidationError

TENANT = "00000000-0000-4000-8000-000000000001"
OTHER_TENANT = "00000000-0000-4000-8000-000000000002"
WORKFLOW = "00000000-0000-4000-8000-000000000003"
SUBJECT = "00000000-0000-4000-8000-000000000004"
NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def contracts():
    # Import in test bodies so absent contracts fail tests rather than collection.
    return import_module("p01.contracts")


@pytest.mark.parametrize("changes", [
    {"title": ""}, {"title": " \t\n"}, {"title": "x" * 161},
    {"body": ""}, {"body": "\u2003\n"}, {"body": "x" * 4001},
    {"priority": "urgent"}, {"priority": 1}, {"title": 123},
    {"tenant_id": TENANT}, {"tool_url": "https://untrusted.invalid"},
])
def test_draft_rejects_invalid_fields(changes):
    c = contracts()
    with pytest.raises(ValidationError):
        c.TicketDraft.model_validate({"title": "Printer issue", "body": "Paper jam", "priority": "normal", **changes})


@pytest.mark.parametrize("priority", ["low", "normal", "high"])
def test_draft_accepts_declared_boundaries(priority):
    c = contracts()
    draft = c.TicketDraft(title="x" * 160, body="x" * 4000, priority=priority)
    assert len(draft.title) == 160
    assert len(draft.body) == 4000
    assert draft.priority == priority
    assert c.TicketDraft(title="x", body="y", priority=priority).body == "y"


def test_validated_draft_cannot_be_mutated():
    c = contracts()
    draft = c.TicketDraft(title="Printer", body="Jam", priority="normal")
    with pytest.raises(ValidationError):
        draft.title = "Different approved intent"


@pytest.mark.parametrize("text", ["", " \n\t", "x" * 4001, 42, None])
def test_request_rejects_invalid_text(text):
    c = contracts()
    with pytest.raises(ValidationError):
        c.RequestInput(text=text)


def test_request_preserves_content_and_rejects_protected_fields():
    c = contracts()
    assert c.RequestInput(text=" Repair printer ").text == " Repair printer "
    assert len(c.RequestInput(text="x" * 4000).text) == 4000
    with pytest.raises(ValidationError):
        c.RequestInput.model_validate({"text": "Repair printer", "tenant_id": TENANT})


def test_canonical_digest_ignores_object_key_order():
    c = contracts()
    expected = "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    assert c.canonical_digest({"a": 1, "b": 2}) == expected
    assert c.canonical_digest({"b": 2, "a": 1}) == expected
    assert c.canonical_digest({"a": 1, "b": 3}) != expected


def test_canonical_digest_handles_nested_json_and_utf8():
    c = contracts()
    assert c.canonical_digest({"b": {"y": "café", "x": [1, 2]}, "a": True}) == c.canonical_digest({"a": True, "b": {"x": [1, 2], "y": "café"}})
    assert c.canonical_digest({"list": [1, 2]}) != c.canonical_digest({"list": [2, 1]})
    assert c.canonical_digest({"title": "café"}) != c.canonical_digest({"title": "cafe"})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_digest_rejects_non_json_numbers(value):
    c = contracts()
    with pytest.raises(ValueError):
        c.canonical_digest({"value": value})


def test_command_key_is_stable_and_tenant_scoped():
    c = contracts()
    first = c.command_key(TENANT, WORKFLOW, 1)
    assert len(first) == 64
    assert int(first, 16) >= 0
    assert first == c.command_key(TENANT, WORKFLOW, 1)
    assert first != c.command_key(OTHER_TENANT, WORKFLOW, 1)
    assert first != c.command_key(TENANT, SUBJECT, 1)


@pytest.mark.parametrize("version", [0, -1, 2, True, "1"])
def test_command_key_rejects_unsupported_action_versions(version):
    c = contracts()
    with pytest.raises(ValueError):
        c.command_key(TENANT, WORKFLOW, version)


def test_identity_requires_uuid_strings():
    c = contracts()
    with pytest.raises(ValidationError):
        c.Principal(tenant_id="invented-tenant", subject_id=SUBJECT, permissions=frozenset({"submit"}))
    with pytest.raises(ValueError):
        c.command_key("invented-tenant", WORKFLOW, 1)
    principal = c.Principal(tenant_id=TENANT, subject_id=SUBJECT, permissions=frozenset({"submit"}))
    assert principal.tenant_id == TENANT
    with pytest.raises(ValidationError):
        c.Principal(tenant_id=TENANT, subject_id=SUBJECT, permissions=frozenset({"admin_everything"}))


@pytest.mark.parametrize("changes", [
    {"draft_digest": "not-a-digest"}, {"decision": "edit"},
    {"actor": SUBJECT}, {"expires_at": NOW},
])
def test_approval_input_does_not_grant_authority(changes):
    c = contracts()
    with pytest.raises(ValidationError):
        c.ApprovalInput.model_validate({"draft_digest": "a" * 64, "decision": "approve", **changes})


def test_approval_accepts_only_approve_or_reject():
    c = contracts()
    for decision in ("approve", "reject"):
        assert c.ApprovalInput(draft_digest="a" * 64, decision=decision).decision == decision


def test_external_command_is_bound_to_stable_identity():
    c = contracts()
    key = c.command_key(TENANT, WORKFLOW, 1)
    draft = c.TicketDraft(title="Printer", body="Jam", priority="normal")
    command = c.ExternalCommand(key=key, tenant_id=TENANT, workflow_id=WORKFLOW, action_version=1, draft=draft)
    assert command.key == key
    with pytest.raises(ValidationError):
        c.ExternalCommand(key="b" * 64, tenant_id=TENANT, workflow_id=WORKFLOW, action_version=1, draft=draft)
    assert c.ExternalCommand.model_validate_json(command.model_dump_json()) == command
    result = c.TicketResult(ticket_id=SUBJECT, command_key=key)
    assert c.TicketResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("target", ["accepted", "drafting", "awaiting_approval", "executing"])
@pytest.mark.parametrize("terminal", ["completed", "rejected", "expired", "failed"])
def test_terminal_state_cannot_regress(terminal, target):
    c = contracts()
    with pytest.raises(c.ContractError) as error:
        c.transition(c.RunStatus(terminal), c.RunStatus(target))
    assert error.value.code == "invalid_transition"


@pytest.mark.parametrize(("current", "target"), [
    ("accepted", "drafting"), ("drafting", "awaiting_approval"),
    ("awaiting_approval", "executing"), ("executing", "completed"),
    ("awaiting_approval", "rejected"), ("awaiting_approval", "expired"),
    ("executing", "needs_review"), ("needs_review", "completed"),
])
def test_declared_forward_transitions(current, target):
    c = contracts()
    assert c.transition(c.RunStatus(current), c.RunStatus(target)) == c.RunStatus(target)


@pytest.mark.parametrize(("current", "target"), [
    ("accepted", "executing"), ("drafting", "completed"),
    ("rejected", "completed"), ("needs_review", "executing"),
])
def test_state_machine_cannot_skip_approval_or_blindly_repeat_an_ambiguous_action(current, target):
    c = contracts()
    with pytest.raises(c.ContractError):
        c.transition(c.RunStatus(current), c.RunStatus(target))


def test_identical_status_projection_is_idempotent():
    c = contracts()
    for state in c.RunStatus:
        assert c.transition(state, state) == state


@pytest.mark.parametrize("stamp", [datetime(2026, 10, 28), NOW.astimezone(timezone(timedelta(hours=1)))])
def test_record_rejects_non_utc_timestamps(stamp):
    c = contracts()
    with pytest.raises(ValidationError):
        c.RunRecord(workflow_id=WORKFLOW, tenant_id=TENANT, subject_id=SUBJECT, request_digest="a" * 64, created_at=stamp, updated_at=NOW)


def test_record_round_trip_preserves_version_and_utc():
    c = contracts()
    record = c.RunRecord(workflow_id=WORKFLOW, tenant_id=TENANT, subject_id=SUBJECT, request_digest="a" * 64, created_at=NOW, updated_at=NOW)
    restored = c.RunRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.version == 1
    assert restored.created_at.utcoffset() == timedelta(0)
    assert restored.model_attempts == restored.tool_attempts == 0


@pytest.mark.parametrize("version", [0, 2, True, "1"])
def test_workflow_state_rejects_unsupported_versions(version):
    c = contracts()
    with pytest.raises(ValidationError):
        c.WorkflowState(workflow_id=WORKFLOW, tenant_id=TENANT, subject_id=SUBJECT, version=version)


@pytest.mark.parametrize("attempts", [-1, 4, True])
def test_attempt_counts_are_bounded(attempts):
    c = contracts()
    with pytest.raises(ValidationError):
        c.RunRecord(workflow_id=WORKFLOW, tenant_id=TENANT, subject_id=SUBJECT, request_digest="a" * 64, created_at=NOW, updated_at=NOW, tool_attempts=attempts)


def test_serialized_workflow_state_is_strict_and_credential_free():
    c = contracts()
    state = c.WorkflowState(workflow_id=WORKFLOW, tenant_id=TENANT, subject_id=SUBJECT)
    assert c.WorkflowState.model_validate_json(state.model_dump_json()) == state
    assert state.model_dump(mode="json")["status"] == "accepted"
    with pytest.raises(ValidationError):
        c.WorkflowState(workflow_id=WORKFLOW, tenant_id=TENANT, subject_id=SUBJECT, token="secret")
