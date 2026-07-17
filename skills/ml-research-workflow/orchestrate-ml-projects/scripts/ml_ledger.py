#!/usr/bin/env python3
"""Append-only local ledger for resumable ML experiment batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PHASES = (
    "planned",
    "implementing",
    "preflight",
    "fit-one-batch",
    "smoke",
    "snapshot",
    "main-run",
    "evaluating",
)
TERMINAL = ("completed", "failed", "interrupted", "cancelled", "invalid")
LIVE_HANDLE_STATUSES = ("queued", "running")
IDENTITY_FIELDS = ("code", "data", "config", "environment")
BUDGET_LIMITS = {
    "max_runs": "runs",
    "max_cost": "cost",
    "max_wall_seconds": "wall_seconds",
}


class LedgerError(Exception):
    """Raised for invalid state or user input."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise LedgerError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"Invalid JSON in {path}: {exc}") from exc


def parse_json_arg(raw: str, label: str) -> Any:
    if raw.startswith("@"):
        return read_json(Path(raw[1:]))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LedgerError(f"Invalid JSON for {label}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def require_nonempty(value: Any, label: str) -> None:
    if value is None or value == "" or value == [] or value == {}:
        raise LedgerError(f"{label} must not be empty")


def validate_identities(identities: Any, label: str = "identities") -> dict[str, Any]:
    if not isinstance(identities, dict):
        raise LedgerError(f"{label} must be an object")
    for field in IDENTITY_FIELDS:
        require_nonempty(identities.get(field), f"{label}.{field}")
    return identities


def validate_consumed_budget(value: Any, label: str = "consumed_budget") -> dict[str, float]:
    if not isinstance(value, dict):
        raise LedgerError(f"{label} must be an object")
    normalized: dict[str, float] = {}
    for field in ("cost", "wall_seconds"):
        amount = value.get(field, 0)
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount < 0:
            raise LedgerError(f"{label}.{field} must be a non-negative number")
        normalized[field] = float(amount)
    return normalized


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LedgerError("result must be an object")
    for field in ("valid", "metrics", "cost", "artifacts", "wandb", "conclusion"):
        if field not in value:
            raise LedgerError(f"result is missing required field: {field}")
    if not isinstance(value["valid"], bool):
        raise LedgerError("result.valid must be a boolean")
    if not isinstance(value["metrics"], dict):
        raise LedgerError("result.metrics must be an object")
    value["cost"] = validate_consumed_budget(value["cost"], "result.cost")
    if not isinstance(value["artifacts"], list):
        raise LedgerError("result.artifacts must be a list")
    if not isinstance(value["wandb"], dict):
        raise LedgerError("result.wandb must be an object")
    require_nonempty(value["wandb"].get("mode"), "result.wandb.mode")
    require_nonempty(value["conclusion"], "result.conclusion")
    return value


def validate_handle(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LedgerError("handle must be an object")
    required = (
        "substrate",
        "host",
        "working_directory",
        "command",
        "status",
        "observed_at",
        "log_location",
        "wandb_run_id",
        "consumed_budget",
    )
    for field in required:
        if field not in value:
            raise LedgerError(f"handle is missing required field: {field}")
        if field not in ("wandb_run_id", "consumed_budget"):
            require_nonempty(value[field], f"handle.{field}")
    if not any(value.get(field) not in (None, "") for field in ("process_id", "session_id", "job_id")):
        raise LedgerError("handle requires process_id, session_id, or job_id")
    if value["status"] not in ("queued", "running", "stopped", "unknown"):
        raise LedgerError("handle.status must be queued, running, stopped, or unknown")
    value["consumed_budget"] = validate_consumed_budget(
        value["consumed_budget"], "handle.consumed_budget"
    )
    return value


def validate_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LedgerError("checkpoint must be an object")
    for field in ("path", "valid", "contains", "identities", "recorded_at"):
        if field not in value:
            raise LedgerError(f"checkpoint is missing required field: {field}")
    require_nonempty(value["path"], "checkpoint.path")
    require_nonempty(value["recorded_at"], "checkpoint.recorded_at")
    if not isinstance(value["valid"], bool):
        raise LedgerError("checkpoint.valid must be a boolean")
    if not isinstance(value["contains"], list) or not value["contains"]:
        raise LedgerError("checkpoint.contains must be a non-empty list")
    value["identities"] = validate_identities(value["identities"], "checkpoint.identities")
    return value


def validate_contract(contract: Any) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise LedgerError("Batch contract must be a JSON object")
    required = (
        "schema_version",
        "batch_id",
        "approval",
        "baseline_id",
        "evaluation_protocol",
        "budget",
        "stopping_conditions",
        "decision_mapping",
        "experiments",
    )
    for field in required:
        if field not in contract:
            raise LedgerError(f"Batch contract is missing required field: {field}")
        require_nonempty(contract[field], field)
    if contract["schema_version"] != 1:
        raise LedgerError("Unsupported schema_version; expected 1")
    approval = contract["approval"]
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        raise LedgerError("approval.status must be 'approved'")
    require_nonempty(approval.get("approved_at"), "approval.approved_at")
    if not isinstance(contract["evaluation_protocol"], dict):
        raise LedgerError("evaluation_protocol must be an object")
    if not isinstance(contract["budget"], dict):
        raise LedgerError("budget must be an object")
    if not isinstance(contract["stopping_conditions"], list):
        raise LedgerError("stopping_conditions must be a list")
    if not isinstance(contract["decision_mapping"], dict):
        raise LedgerError("decision_mapping must be an object")
    experiments = contract["experiments"]
    if not isinstance(experiments, list) or not experiments:
        raise LedgerError("experiments must be a non-empty list")

    by_id: dict[str, dict[str, Any]] = {}
    for index, experiment in enumerate(experiments):
        if not isinstance(experiment, dict):
            raise LedgerError(f"experiments[{index}] must be an object")
        for field in (
            "experiment_id",
            "hypothesis",
            "kind",
            "parent_id",
            "config",
            "depends_on",
            "retry",
        ):
            if field not in experiment:
                raise LedgerError(f"experiments[{index}] is missing required field: {field}")
        experiment_id = experiment["experiment_id"]
        require_nonempty(experiment_id, f"experiments[{index}].experiment_id")
        require_nonempty(experiment["hypothesis"], f"experiments[{index}].hypothesis")
        require_nonempty(experiment["parent_id"], f"experiments[{index}].parent_id")
        if experiment["kind"] not in ("trainable", "evaluation-only"):
            raise LedgerError(f"{experiment_id}.kind must be trainable or evaluation-only")
        if not isinstance(experiment["config"], dict):
            raise LedgerError(f"{experiment_id}.config must be an object")
        if not isinstance(experiment["depends_on"], list):
            raise LedgerError(f"{experiment_id}.depends_on must be a list")
        retry = experiment["retry"]
        max_attempts = retry.get("max_attempts") if isinstance(retry, dict) else None
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
            raise LedgerError(f"{experiment_id}.retry.max_attempts must be a positive integer")
        if experiment_id in by_id:
            raise LedgerError(f"Duplicate experiment_id: {experiment_id}")
        by_id[experiment_id] = experiment

    for experiment_id, experiment in by_id.items():
        parent_id = experiment["parent_id"]
        if parent_id != contract["baseline_id"] and parent_id not in by_id:
            raise LedgerError(f"{experiment_id} has unknown parent_id: {parent_id}")
        if parent_id == experiment_id:
            raise LedgerError(f"{experiment_id} cannot be its own parent")
        if parent_id in by_id and parent_id not in experiment["depends_on"]:
            raise LedgerError(
                f"{experiment_id} must depend_on its logical parent {parent_id}"
            )
        for dependency in experiment["depends_on"]:
            if dependency not in by_id:
                raise LedgerError(f"{experiment_id} depends on unknown experiment: {dependency}")
            if dependency == experiment_id:
                raise LedgerError(f"{experiment_id} cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(experiment_id: str) -> None:
        if experiment_id in visiting:
            raise LedgerError("Experiment dependency graph contains a cycle")
        if experiment_id in visited:
            return
        visiting.add(experiment_id)
        for dependency in by_id[experiment_id]["depends_on"]:
            visit(dependency)
        visiting.remove(experiment_id)
        visited.add(experiment_id)

    for experiment_id in by_id:
        visit(experiment_id)

    known_limits = set(contract["budget"]) & set(BUDGET_LIMITS)
    if not known_limits:
        raise LedgerError(
            "budget must define at least one of max_runs, max_cost, or max_wall_seconds"
        )
    for limit in known_limits:
        amount = contract["budget"][limit]
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
            raise LedgerError(f"budget.{limit} must be a positive number")
        if limit == "max_runs" and not isinstance(amount, int):
            raise LedgerError("budget.max_runs must be an integer")
    allow_concurrent = contract.get("allow_concurrent_batches", False)
    if not isinstance(allow_concurrent, bool):
        raise LedgerError("allow_concurrent_batches must be a boolean when provided")
    return contract


def ledger_path(root: Path) -> Path:
    return root / "ledger.jsonl"


def repair_torn_tail(path: Path) -> None:
    """Recover a valid JSONL prefix after an interrupted final append."""
    if not path.exists():
        return
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    last_newline = data.rfind(b"\n")
    prefix_end = last_newline + 1
    tail = data[prefix_end:]
    try:
        event = json.loads(tail.decode("utf-8"))
        if not isinstance(event, dict) or "event_type" not in event:
            raise ValueError("invalid event")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        repaired = data[:prefix_end]
    else:
        repaired = data + b"\n"
    with path.open("r+b") as handle:
        handle.seek(0)
        handle.write(repaired)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())


def load_events(root: Path) -> list[dict[str, Any]]:
    path = ledger_path(root)
    if not path.exists():
        return []
    repair_torn_tail(path)
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"Invalid ledger JSON at line {line_number}: {exc}") from exc
            if not isinstance(event, dict) or "event_type" not in event:
                raise LedgerError(f"Invalid ledger event at line {line_number}")
            events.append(event)
    return events


def append_event(root: Path, event: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = ledger_path(root)
    repair_torn_tail(path)
    line = canonical_json(event) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def new_event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "timestamp": utc_now(),
        "event_type": event_type,
        **fields,
    }


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "last_event_at": None,
        "project": None,
        "batches": {},
        "attempts": {},
    }


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    state = empty_state()
    for event in events:
        state["last_event_at"] = event["timestamp"]
        event_type = event["event_type"]
        if event_type == "project_initialized":
            state["project"] = dict(event["project"])
            state["project"]["initialized_at"] = event["timestamp"]
        elif event_type == "project_updated":
            if state["project"] is None:
                raise LedgerError("project_updated appeared before project_initialized")
            state["project"].update(event["changes"])
        elif event_type == "batch_registered":
            contract = event["contract"]
            batch_id = contract["batch_id"]
            experiments = {}
            for item in contract["experiments"]:
                experiments[item["experiment_id"]] = {
                    "experiment_id": item["experiment_id"],
                    "status": "planned",
                    "attempt_ids": [],
                    "depends_on": list(item["depends_on"]),
                    "max_attempts": item["retry"]["max_attempts"],
                    "kind": item["kind"],
                    "parent_id": item["parent_id"],
                }
            state["batches"][batch_id] = {
                "batch_id": batch_id,
                "contract_sha256": event["contract_sha256"],
                "contract": contract,
                "registered_at": event["timestamp"],
                "closed_at": None,
                "close_reason": None,
                "experiments": experiments,
            }
            if state["project"] is not None:
                state["project"].update(
                    {"active_batch_id": batch_id, "status": "batch-approved"}
                )
        elif event_type == "attempt_started":
            batch = state["batches"][event["batch_id"]]
            experiment = batch["experiments"][event["experiment_id"]]
            attempt_id = event["attempt_id"]
            attempt = {
                "attempt_id": attempt_id,
                "batch_id": event["batch_id"],
                "experiment_id": event["experiment_id"],
                "status": "running",
                "phase": "planned",
                "phase_history": [
                    {"phase": "planned", "timestamp": event["timestamp"], "metadata": {}}
                ],
                "identities": event.get("identities", {}),
                "parent_attempt_id": event.get("parent_attempt_id"),
                "execution_handle": None,
                "checkpoint": None,
                "budget_consumed": {"cost": 0.0, "wall_seconds": 0.0},
                "result": None,
                "started_at": event["timestamp"],
                "finished_at": None,
            }
            state["attempts"][attempt_id] = attempt
            experiment["attempt_ids"].append(attempt_id)
            experiment["status"] = "running"
        elif event_type == "phase_changed":
            attempt = state["attempts"][event["attempt_id"]]
            attempt["phase"] = event["phase"]
            attempt["phase_history"].append(
                {
                    "phase": event["phase"],
                    "timestamp": event["timestamp"],
                    "metadata": event.get("metadata", {}),
                }
            )
        elif event_type == "execution_observed":
            attempt = state["attempts"][event["attempt_id"]]
            attempt["execution_handle"] = event["handle"]
            attempt["budget_consumed"] = event["handle"]["consumed_budget"]
        elif event_type == "budget_recorded":
            state["attempts"][event["attempt_id"]]["budget_consumed"] = event["consumed"]
        elif event_type == "checkpoint_recorded":
            state["attempts"][event["attempt_id"]]["checkpoint"] = event["checkpoint"]
        elif event_type == "attempt_finished":
            attempt = state["attempts"][event["attempt_id"]]
            attempt["status"] = event["status"]
            attempt["result"] = event.get("result", {})
            attempt["budget_consumed"] = event["result"]["cost"]
            attempt["finished_at"] = event["timestamp"]
            batch = state["batches"][attempt["batch_id"]]
            experiment = batch["experiments"][attempt["experiment_id"]]
            experiment["status"] = event["status"]
        elif event_type == "batch_closed":
            batch = state["batches"][event["batch_id"]]
            batch["closed_at"] = event["timestamp"]
            batch["close_reason"] = event["reason"]
            if (
                state["project"] is not None
                and state["project"].get("active_batch_id") == event["batch_id"]
            ):
                state["project"]["active_batch_id"] = None
                state["project"]["status"] = "batch-closed"
        else:
            raise LedgerError(f"Unknown event_type in ledger: {event_type}")
    for batch in state["batches"].values():
        batch["budget"] = calculate_budget(state, batch["batch_id"])
        batch["next_action"] = compute_next_action(state, batch["batch_id"])
    return state


def find_attempt(state: dict[str, Any], attempt_id: str) -> dict[str, Any]:
    attempt = state["attempts"].get(attempt_id)
    if attempt is None:
        raise LedgerError(f"Unknown attempt_id: {attempt_id}")
    return attempt


def matching_checkpoint(attempt: dict[str, Any]) -> bool:
    checkpoint = attempt.get("checkpoint")
    if not isinstance(checkpoint, dict) or checkpoint.get("valid") is not True:
        return False
    checkpoint_identities = checkpoint.get("identities")
    contains = set(checkpoint.get("contains", []))
    return (
        isinstance(checkpoint_identities, dict)
        and checkpoint_identities == attempt.get("identities", {})
        and {"model", "optimizer"}.issubset(contains)
    )


def calculate_budget(state: dict[str, Any], batch_id: str) -> dict[str, Any]:
    batch = state["batches"][batch_id]
    attempts = [
        state["attempts"][attempt_id]
        for experiment in batch["experiments"].values()
        for attempt_id in experiment["attempt_ids"]
    ]
    consumed = {
        "runs": len(attempts),
        "cost": sum(item["budget_consumed"]["cost"] for item in attempts),
        "wall_seconds": sum(item["budget_consumed"]["wall_seconds"] for item in attempts),
    }
    limits = batch["contract"]["budget"]
    remaining: dict[str, float | int] = {}
    exhausted: list[str] = []
    for limit, consumed_field in BUDGET_LIMITS.items():
        if limit not in limits:
            continue
        amount = max(limits[limit] - consumed[consumed_field], 0)
        remaining[limit] = int(amount) if limit == "max_runs" else float(amount)
        if amount <= 0:
            exhausted.append(limit)
    return {
        "limits": limits,
        "consumed": consumed,
        "remaining": remaining,
        "exhausted": exhausted,
    }


def compute_next_action(state: dict[str, Any], batch_id: str) -> dict[str, Any]:
    batch = state["batches"].get(batch_id)
    if batch is None:
        raise LedgerError(f"Unknown batch_id: {batch_id}")
    experiments = batch["experiments"]
    contract = batch["contract"]
    budget = calculate_budget(state, batch_id)

    if batch.get("closed_at"):
        return {
            "action": "batch-closed",
            "closed_at": batch["closed_at"],
            "reason": batch["close_reason"],
            "budget": budget,
        }

    if all(item["status"] == "completed" for item in experiments.values()):
        return {"action": "batch-complete", "budget": budget}

    for planned in contract["experiments"]:
        experiment = experiments[planned["experiment_id"]]
        attempt_ids = experiment["attempt_ids"]
        if experiment["status"] == "completed":
            continue
        if attempt_ids:
            attempt = state["attempts"][attempt_ids[-1]]
            if attempt["status"] == "running":
                handle = attempt.get("execution_handle") or {}
                runtime_exhausted = [
                    limit for limit in budget["exhausted"] if limit != "max_runs"
                ]
                if attempt["phase"] != "evaluating" and runtime_exhausted:
                    return {
                        "action": "blocked",
                        "experiment_id": experiment["experiment_id"],
                        "attempt_id": attempt["attempt_id"],
                        "reason": "budget-exhausted",
                        "budget": budget,
                    }
                if handle.get("status") in LIVE_HANDLE_STATUSES:
                    return {
                        "action": "monitor-attempt",
                        "experiment_id": experiment["experiment_id"],
                        "attempt_id": attempt["attempt_id"],
                        "phase": attempt["phase"],
                        "budget": budget,
                    }
                if attempt["phase"] == "main-run":
                    if not handle:
                        return {
                            "action": "inspect-execution",
                            "experiment_id": experiment["experiment_id"],
                            "attempt_id": attempt["attempt_id"],
                            "phase": attempt["phase"],
                            "budget": budget,
                        }
                    if handle.get("status") in ("stopped", "unknown"):
                        if matching_checkpoint(attempt):
                            return {
                                "action": "resume-attempt",
                                "experiment_id": experiment["experiment_id"],
                                "attempt_id": attempt["attempt_id"],
                                "phase": attempt["phase"],
                                "budget": budget,
                            }
                        return {
                            "action": "mark-interrupted",
                            "experiment_id": experiment["experiment_id"],
                            "attempt_id": attempt["attempt_id"],
                            "reason": "no-matching-checkpoint",
                            "budget": budget,
                        }
                if handle.get("status") in ("stopped", "unknown"):
                    return {
                        "action": "mark-interrupted",
                        "experiment_id": experiment["experiment_id"],
                        "attempt_id": attempt["attempt_id"],
                        "reason": "execution-stopped",
                        "budget": budget,
                    }
                return {
                    "action": "continue-attempt",
                    "experiment_id": experiment["experiment_id"],
                    "attempt_id": attempt["attempt_id"],
                    "phase": attempt["phase"],
                    "budget": budget,
                }
            if attempt["status"] != "completed":
                retry_available = len(attempt_ids) < experiment["max_attempts"]
                budget_available = not budget["exhausted"]
                if retry_available and budget_available:
                    return {
                        "action": "retry-experiment",
                        "experiment_id": experiment["experiment_id"],
                        "previous_attempt_id": attempt["attempt_id"],
                        "budget": budget,
                    }
                return {
                    "action": "blocked",
                    "experiment_id": experiment["experiment_id"],
                    "reason": "retry-or-budget-exhausted",
                    "budget": budget,
                }
        dependencies_complete = all(
            experiments[dependency]["status"] == "completed"
            for dependency in experiment["depends_on"]
        )
        if not dependencies_complete:
            continue
        if budget["exhausted"]:
            return {
                "action": "blocked",
                "experiment_id": experiment["experiment_id"],
                "reason": "budget-exhausted",
                "budget": budget,
            }
        return {
            "action": "start-experiment",
            "experiment_id": experiment["experiment_id"],
            "budget": budget,
        }
    return {
        "action": "blocked",
        "reason": "dependencies-not-complete",
        "budget": budget,
    }


def project_state(root: Path, state: dict[str, Any]) -> None:
    for batch_id, batch in state["batches"].items():
        atomic_write_json(root / "batches" / batch_id / "contract.json", batch["contract"])
        batch_projection = {
            "schema_version": 1,
            "batch_id": batch_id,
            "contract_sha256": batch["contract_sha256"],
            "registered_at": batch["registered_at"],
            "closed_at": batch["closed_at"],
            "close_reason": batch["close_reason"],
            "experiments": batch["experiments"],
            "budget": batch["budget"],
            "next_action": batch["next_action"],
        }
        atomic_write_json(root / "batches" / batch_id / "state.json", batch_projection)
    for attempt_id, attempt in state["attempts"].items():
        atomic_write_json(root / "runs" / attempt_id / "state.json", attempt)
    if state["project"] is not None:
        project = state["project"]
        active_batch_id = project.get("active_batch_id")
        next_action = (
            state["batches"][active_batch_id]["next_action"]
            if active_batch_id in state["batches"]
            else {"action": "accept-project-direction"}
        )
        active_budget = (
            state["batches"][active_batch_id]["budget"]
            if active_batch_id in state["batches"]
            else None
        )
        lines = [
            "# ML Project",
            "",
            "## Durable project state",
            "",
            f"- Title: {project['title']}",
            f"- Project mode: {project['mode']}",
            f"- Status: {project.get('status', 'discovery')}",
            f"- Current baseline: {project.get('baseline_id') or 'not established'}",
            f"- Active batch: {active_batch_id or 'none'}",
            f"- Active budget: {canonical_json(active_budget) if active_budget else 'none'}",
            f"- Decision state: {canonical_json(project.get('decision_state', {}))}",
            f"- Next action: {next_action['action']}",
            f"- Last updated: {state['last_event_at']}",
            "",
            "This file is projected from `ledger.jsonl`; use the ledger utility for state changes.",
            "",
        ]
        project_path = root / "project.md"
        fd, temp_name = tempfile.mkstemp(prefix=".project.md.", dir=root)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, project_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()


def rebuild(root: Path) -> dict[str, Any]:
    state = replay(load_events(root))
    project_state(root, state)
    return state


def append_and_rebuild(root: Path, event: dict[str, Any]) -> dict[str, Any]:
    append_event(root, event)
    return rebuild(root)


def initialize(root: Path, title: str, mode: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "batches").mkdir(exist_ok=True)
    (root / "runs").mkdir(exist_ok=True)
    ledger_path(root).touch(exist_ok=True)
    events = load_events(root)
    if events:
        state = replay(events)
        if state["project"] is None:
            raise LedgerError("Initialized ledger is missing project state")
        if state["project"]["title"] != title or state["project"]["mode"] != mode:
            raise LedgerError("Workflow is already initialized with different project identity")
        project_state(root, state)
        return
    append_and_rebuild(
        root,
        new_event(
            "project_initialized",
            project={
                "title": title,
                "mode": mode,
                "status": "discovery",
                "baseline_id": None,
                "active_batch_id": None,
            },
        ),
    )


def update_project(root: Path, changes: dict[str, Any]) -> dict[str, Any]:
    ensure_initialized(root)
    state = replay(load_events(root))
    if state["project"] is None:
        raise LedgerError("Project state is missing")
    allowed = {"status", "baseline_id", "active_batch_id", "decision_state"}
    unknown = set(changes) - allowed
    if unknown:
        raise LedgerError(f"Unsupported project fields: {sorted(unknown)}")
    if "active_batch_id" in changes and changes["active_batch_id"] is not None:
        active_batch_id = changes["active_batch_id"]
        batch = state["batches"].get(active_batch_id)
        if batch is None:
            raise LedgerError(f"Unknown active_batch_id: {active_batch_id}")
        if batch["next_action"]["action"] == "batch-closed":
            raise LedgerError(f"Cannot activate closed batch: {active_batch_id}")
    event = new_event("project_updated", changes=changes)
    return append_and_rebuild(root, event)


def ensure_initialized(root: Path) -> None:
    if not ledger_path(root).exists():
        raise LedgerError(f"Workflow is not initialized: {root}")


def register_batch(root: Path, contract_path: Path) -> dict[str, Any]:
    ensure_initialized(root)
    contract = validate_contract(read_json(contract_path))
    state = replay(load_events(root))
    batch_id = contract["batch_id"]
    if batch_id in state["batches"]:
        raise LedgerError(f"Batch already registered: {batch_id}")
    active_batches = [
        existing_id
        for existing_id, existing in state["batches"].items()
        if existing["next_action"]["action"] not in ("batch-complete", "batch-closed")
    ]
    if active_batches and not contract.get("allow_concurrent_batches", False):
        raise LedgerError(
            f"Cannot register another active batch while {active_batches} remain active; "
            "the approved contract must explicitly allow concurrent batches"
        )
    event = new_event(
        "batch_registered",
        batch_id=batch_id,
        contract_sha256=sha256_json(contract),
        contract=contract,
    )
    return append_and_rebuild(root, event)


def close_batch(root: Path, batch_id: str, reason: str) -> dict[str, Any]:
    ensure_initialized(root)
    require_nonempty(reason, "reason")
    state = replay(load_events(root))
    batch = state["batches"].get(batch_id)
    if batch is None:
        raise LedgerError(f"Unknown batch_id: {batch_id}")
    if batch.get("closed_at"):
        raise LedgerError(f"Batch is already closed: {batch_id}")
    running = [
        attempt_id
        for experiment in batch["experiments"].values()
        for attempt_id in experiment["attempt_ids"]
        if state["attempts"][attempt_id]["status"] == "running"
    ]
    if running:
        raise LedgerError(f"Cannot close batch with running attempts: {running}")
    event = new_event("batch_closed", batch_id=batch_id, reason=reason)
    return append_and_rebuild(root, event)


def start_attempt(
    root: Path,
    batch_id: str,
    experiment_id: str,
    attempt_id: str,
    identities: dict[str, Any],
    parent_attempt_id: str | None,
) -> dict[str, Any]:
    ensure_initialized(root)
    state = replay(load_events(root))
    if attempt_id in state["attempts"]:
        raise LedgerError(f"Attempt already exists: {attempt_id}")
    batch = state["batches"].get(batch_id)
    if batch is None or experiment_id not in batch["experiments"]:
        raise LedgerError(f"Unknown experiment {experiment_id} in batch {batch_id}")
    next_action = compute_next_action(state, batch_id)
    if next_action.get("experiment_id") != experiment_id or next_action["action"] not in (
        "start-experiment",
        "retry-experiment",
    ):
        raise LedgerError(
            f"Experiment {experiment_id} is not eligible to start; next action is {next_action}"
        )
    expected_parent = next_action.get("previous_attempt_id")
    if expected_parent != parent_attempt_id:
        raise LedgerError(
            f"parent_attempt_id must be {expected_parent!r} for action {next_action['action']}"
        )
    identities = validate_identities(identities)
    event = new_event(
        "attempt_started",
        batch_id=batch_id,
        experiment_id=experiment_id,
        attempt_id=attempt_id,
        identities=identities,
        parent_attempt_id=parent_attempt_id,
    )
    return append_and_rebuild(root, event)


def allowed_next_phases(kind: str, phase: str) -> tuple[str, ...]:
    mapping = {
        "planned": ("implementing",),
        "implementing": ("preflight",),
        "preflight": ("fit-one-batch",) if kind == "trainable" else ("smoke",),
        "fit-one-batch": ("smoke",),
        "smoke": ("snapshot",),
        "snapshot": ("main-run",),
        "main-run": ("evaluating",),
        "evaluating": (),
    }
    return mapping[phase]


def transition_attempt(
    root: Path, attempt_id: str, phase: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    ensure_initialized(root)
    if phase not in PHASES:
        raise LedgerError(f"Unknown phase: {phase}")
    state = replay(load_events(root))
    attempt = find_attempt(state, attempt_id)
    if attempt["status"] != "running":
        raise LedgerError(f"Attempt is terminal: {attempt_id}")
    batch = state["batches"][attempt["batch_id"]]
    kind = batch["experiments"][attempt["experiment_id"]]["kind"]
    budget = calculate_budget(state, attempt["batch_id"])
    runtime_exhausted = [limit for limit in budget["exhausted"] if limit != "max_runs"]
    if runtime_exhausted and phase != "evaluating":
        raise LedgerError(
            f"Cannot enter {phase}; batch budget is exhausted: {runtime_exhausted}"
        )
    allowed = allowed_next_phases(kind, attempt["phase"])
    if phase not in allowed:
        raise LedgerError(
            f"Illegal phase transition for {kind}: {attempt['phase']} -> {phase}; allowed: {allowed}"
        )
    event = new_event(
        "phase_changed",
        batch_id=attempt["batch_id"],
        experiment_id=attempt["experiment_id"],
        attempt_id=attempt_id,
        phase=phase,
        metadata=metadata,
    )
    return append_and_rebuild(root, event)


def observe_execution(root: Path, attempt_id: str, handle: dict[str, Any]) -> dict[str, Any]:
    ensure_initialized(root)
    state = replay(load_events(root))
    attempt = find_attempt(state, attempt_id)
    if attempt["status"] != "running":
        raise LedgerError(f"Cannot observe terminal attempt: {attempt_id}")
    handle = validate_handle(handle)
    previous = attempt["budget_consumed"]
    consumed = handle["consumed_budget"]
    if any(consumed[field] < previous[field] for field in consumed):
        raise LedgerError("Execution observation budget cannot decrease")
    event = new_event(
        "execution_observed",
        batch_id=attempt["batch_id"],
        experiment_id=attempt["experiment_id"],
        attempt_id=attempt_id,
        handle=handle,
    )
    return append_and_rebuild(root, event)


def record_checkpoint(
    root: Path, attempt_id: str, checkpoint: dict[str, Any]
) -> dict[str, Any]:
    ensure_initialized(root)
    state = replay(load_events(root))
    attempt = find_attempt(state, attempt_id)
    if attempt["status"] != "running":
        raise LedgerError(f"Cannot checkpoint terminal attempt: {attempt_id}")
    checkpoint = validate_checkpoint(checkpoint)
    event = new_event(
        "checkpoint_recorded",
        batch_id=attempt["batch_id"],
        experiment_id=attempt["experiment_id"],
        attempt_id=attempt_id,
        checkpoint=checkpoint,
    )
    return append_and_rebuild(root, event)


def record_budget(root: Path, attempt_id: str, consumed: dict[str, Any]) -> dict[str, Any]:
    ensure_initialized(root)
    state = replay(load_events(root))
    attempt = find_attempt(state, attempt_id)
    if attempt["status"] != "running":
        raise LedgerError(f"Cannot update budget for terminal attempt: {attempt_id}")
    consumed = validate_consumed_budget(consumed)
    previous = attempt["budget_consumed"]
    if any(consumed[field] < previous[field] for field in consumed):
        raise LedgerError("Consumed budget cannot decrease")
    event = new_event(
        "budget_recorded",
        batch_id=attempt["batch_id"],
        experiment_id=attempt["experiment_id"],
        attempt_id=attempt_id,
        consumed=consumed,
    )
    return append_and_rebuild(root, event)


def finish_attempt(
    root: Path, attempt_id: str, status: str, result: dict[str, Any]
) -> dict[str, Any]:
    ensure_initialized(root)
    if status not in TERMINAL:
        raise LedgerError(f"Unknown terminal status: {status}")
    state = replay(load_events(root))
    attempt = find_attempt(state, attempt_id)
    if attempt["status"] != "running":
        raise LedgerError(f"Attempt is already terminal: {attempt_id}")
    if status == "completed" and attempt["phase"] != "evaluating":
        raise LedgerError("A completed attempt must reach the evaluating phase first")
    result = validate_result(result)
    previous_cost = attempt["budget_consumed"]
    if any(result["cost"][field] < previous_cost[field] for field in previous_cost):
        raise LedgerError("Terminal result cost cannot decrease previously consumed budget")
    event = new_event(
        "attempt_finished",
        batch_id=attempt["batch_id"],
        experiment_id=attempt["experiment_id"],
        attempt_id=attempt_id,
        status=status,
        result=result,
    )
    return append_and_rebuild(root, event)


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("ml-workflow"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--title", required=True)
    init_parser.add_argument("--mode", choices=("greenfield", "existing"), required=True)

    register_parser = subparsers.add_parser("register-batch")
    register_parser.add_argument("contract", type=Path)

    close_parser = subparsers.add_parser("close-batch")
    close_parser.add_argument("batch_id")
    close_parser.add_argument("--reason", required=True)

    project_parser = subparsers.add_parser("update-project")
    project_parser.add_argument("--changes", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("batch_id")
    start_parser.add_argument("experiment_id")
    start_parser.add_argument("attempt_id")
    start_parser.add_argument("--identities", required=True)
    start_parser.add_argument("--parent-attempt-id")

    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("attempt_id")
    transition_parser.add_argument("phase", choices=PHASES)
    transition_parser.add_argument("--metadata", default="{}")

    observe_parser = subparsers.add_parser("observe")
    observe_parser.add_argument("attempt_id")
    observe_parser.add_argument("--handle", required=True)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("attempt_id")
    checkpoint_parser.add_argument("--checkpoint", required=True)

    budget_parser = subparsers.add_parser("budget")
    budget_parser.add_argument("attempt_id")
    budget_parser.add_argument("--consumed", required=True)

    finish_parser = subparsers.add_parser("finish")
    finish_parser.add_argument("attempt_id")
    finish_parser.add_argument("status", choices=TERMINAL)
    finish_parser.add_argument("--result", default="{}")

    subparsers.add_parser("rebuild")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--batch-id")

    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("batch_id")

    subparsers.add_parser("list")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("attempt_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "init":
            initialize(root, args.title, args.mode)
            print_json({"root": str(root), "status": "initialized"})
        elif args.command == "register-batch":
            state = register_batch(root, args.contract)
            print_json(state["batches"][read_json(args.contract)["batch_id"]])
        elif args.command == "close-batch":
            state = close_batch(root, args.batch_id, args.reason)
            print_json(state["batches"][args.batch_id])
        elif args.command == "update-project":
            changes = parse_json_arg(args.changes, "changes")
            if not isinstance(changes, dict):
                raise LedgerError("changes must be an object")
            state = update_project(root, changes)
            print_json(state["project"])
        elif args.command == "start":
            identities = parse_json_arg(args.identities, "identities")
            if not isinstance(identities, dict):
                raise LedgerError("identities must be an object")
            state = start_attempt(
                root,
                args.batch_id,
                args.experiment_id,
                args.attempt_id,
                identities,
                args.parent_attempt_id,
            )
            print_json(state["attempts"][args.attempt_id])
        elif args.command == "transition":
            metadata = parse_json_arg(args.metadata, "metadata")
            if not isinstance(metadata, dict):
                raise LedgerError("metadata must be an object")
            state = transition_attempt(root, args.attempt_id, args.phase, metadata)
            print_json(state["attempts"][args.attempt_id])
        elif args.command == "observe":
            handle = parse_json_arg(args.handle, "handle")
            if not isinstance(handle, dict):
                raise LedgerError("handle must be an object")
            state = observe_execution(root, args.attempt_id, handle)
            print_json(state["attempts"][args.attempt_id])
        elif args.command == "checkpoint":
            checkpoint = parse_json_arg(args.checkpoint, "checkpoint")
            if not isinstance(checkpoint, dict):
                raise LedgerError("checkpoint must be an object")
            state = record_checkpoint(root, args.attempt_id, checkpoint)
            print_json(state["attempts"][args.attempt_id])
        elif args.command == "budget":
            consumed = parse_json_arg(args.consumed, "consumed")
            if not isinstance(consumed, dict):
                raise LedgerError("consumed must be an object")
            state = record_budget(root, args.attempt_id, consumed)
            print_json(state["attempts"][args.attempt_id])
        elif args.command == "finish":
            result = parse_json_arg(args.result, "result")
            if not isinstance(result, dict):
                raise LedgerError("result must be an object")
            state = finish_attempt(root, args.attempt_id, args.status, result)
            print_json(state["attempts"][args.attempt_id])
        elif args.command == "rebuild":
            print_json(rebuild(root))
        elif args.command == "status":
            state = replay(load_events(root))
            if args.batch_id:
                batch = state["batches"].get(args.batch_id)
                if batch is None:
                    raise LedgerError(f"Unknown batch_id: {args.batch_id}")
                print_json(batch)
            else:
                print_json(state)
        elif args.command == "next":
            state = replay(load_events(root))
            print_json(compute_next_action(state, args.batch_id))
        elif args.command == "list":
            state = replay(load_events(root))
            print_json(
                {
                    "batches": sorted(state["batches"]),
                    "attempts": sorted(state["attempts"]),
                }
            )
        elif args.command == "inspect":
            state = replay(load_events(root))
            print_json(find_attempt(state, args.attempt_id))
        else:
            parser.error(f"Unhandled command: {args.command}")
        return 0
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
