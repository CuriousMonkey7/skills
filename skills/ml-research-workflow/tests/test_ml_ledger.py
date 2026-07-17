from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "orchestrate-ml-projects" / "scripts" / "ml_ledger.py"


def identities(label: str = "cfg") -> dict:
    return {"code": "code-1", "data": "data-1", "config": label, "environment": "env-1"}


def result(valid: bool = True, conclusion: str = "finished") -> dict:
    return {
        "valid": valid,
        "metrics": {"score": 1} if valid else {},
        "cost": {"cost": 0.0, "wall_seconds": 1.0},
        "artifacts": [],
        "wandb": {"mode": "unavailable", "run_id": None, "url": None},
        "conclusion": conclusion,
    }


def contract(max_runs: int = 5) -> dict:
    experiments = []
    for index in range(1, 4):
        experiment_id = f"exp-{index}"
        experiments.append(
            {
                "experiment_id": experiment_id,
                "hypothesis": f"hypothesis {index}",
                "kind": "trainable",
                "parent_id": "baseline" if index == 1 else f"exp-{index - 1}",
                "config": {"value": index},
                "depends_on": [] if index == 1 else [f"exp-{index - 1}"],
                "retry": {"max_attempts": 2},
            }
        )
    return {
        "schema_version": 1,
        "batch_id": "batch-1",
        "approval": {
            "status": "approved",
            "approved_at": "2026-07-17T00:00:00Z",
            "approved_by": "user",
        },
        "baseline_id": "baseline",
        "evaluation_protocol": {
            "primary_metric": "score",
            "direction": "maximize",
        },
        "budget": {"max_runs": max_runs},
        "stopping_conditions": ["budget exhausted"],
        "decision_mapping": {"improves": "promote", "otherwise": "retain"},
        "experiments": experiments,
    }


class LedgerCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "ml-workflow"
        self.contract_path = self.base / "contract.json"
        self.contract_path.write_text(json.dumps(contract()), encoding="utf-8")
        self.run_cli("init", "--title", "fixture", "--mode", "greenfield")
        self.run_cli("register-batch", str(self.contract_path))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(f"CLI failed: {completed.args}\n{completed.stdout}\n{completed.stderr}")
        return completed

    def output(self, *args: str) -> dict:
        return json.loads(self.run_cli(*args).stdout)

    def advance_completed(self, experiment: str, attempt: str) -> None:
        identity = json.dumps(identities(experiment))
        self.run_cli("start", "batch-1", experiment, attempt, "--identities", identity)
        for phase in (
            "implementing",
            "preflight",
            "fit-one-batch",
            "smoke",
            "snapshot",
            "main-run",
            "evaluating",
        ):
            self.run_cli("transition", attempt, phase)
        self.run_cli("finish", attempt, "completed", "--result", json.dumps(result()))

    def test_three_experiment_resume_does_not_repeat_completed_work(self) -> None:
        self.advance_completed("exp-1", "attempt-1")
        identity = identities("exp-2")
        self.run_cli(
            "start",
            "batch-1",
            "exp-2",
            "attempt-2",
            "--identities",
            json.dumps(identity),
        )
        for phase in (
            "implementing",
            "preflight",
            "fit-one-batch",
            "smoke",
            "snapshot",
            "main-run",
        ):
            self.run_cli("transition", "attempt-2", phase)
        self.run_cli(
            "observe",
            "attempt-2",
            "--handle",
            json.dumps(
                {
                    "substrate": "local",
                    "host": "localhost",
                    "working_directory": "/tmp/fixture",
                    "command": "python train.py",
                    "process_id": "123",
                    "log_location": "/tmp/train.log",
                    "wandb_run_id": None,
                    "consumed_budget": {"cost": 0.0, "wall_seconds": 10.0},
                    "status": "stopped",
                    "observed_at": "2026-07-17T01:00:00Z",
                }
            ),
        )
        self.run_cli(
            "checkpoint",
            "attempt-2",
            "--checkpoint",
            json.dumps(
                {
                    "path": "checkpoint.pt",
                    "valid": True,
                    "contains": ["model", "optimizer"],
                    "identities": identity,
                    "recorded_at": "2026-07-17T00:59:00Z",
                }
            ),
        )
        (self.root / "batches" / "batch-1" / "state.json").unlink()
        rebuilt = self.output("rebuild")
        self.assertEqual(rebuilt["batches"]["batch-1"]["experiments"]["exp-1"]["status"], "completed")
        self.assertEqual(rebuilt["batches"]["batch-1"]["experiments"]["exp-3"]["status"], "planned")
        self.assertEqual(rebuilt["batches"]["batch-1"]["next_action"]["action"], "resume-attempt")
        self.assertEqual(rebuilt["batches"]["batch-1"]["next_action"]["attempt_id"], "attempt-2")

    def test_live_handle_is_monitored_before_other_work(self) -> None:
        identity = json.dumps(identities("live"))
        self.run_cli("start", "batch-1", "exp-1", "attempt-live", "--identities", identity)
        self.run_cli(
            "observe",
            "attempt-live",
            "--handle",
            '{"substrate":"local","host":"localhost","working_directory":"/tmp","command":"train","process_id":"123","log_location":"/tmp/train.log","wandb_run_id":null,"consumed_budget":{"cost":0,"wall_seconds":1},"status":"running","observed_at":"now"}',
        )
        next_action = self.output("next", "batch-1")
        self.assertEqual(next_action["action"], "monitor-attempt")
        self.assertEqual(next_action["attempt_id"], "attempt-live")

    def test_mismatched_checkpoint_does_not_resume(self) -> None:
        identity = identities("mismatch")
        self.run_cli("start", "batch-1", "exp-1", "attempt-mismatch", "--identities", json.dumps(identity))
        for phase in ("implementing", "preflight", "fit-one-batch", "smoke", "snapshot", "main-run"):
            self.run_cli("transition", "attempt-mismatch", phase)
        self.run_cli(
            "checkpoint",
            "attempt-mismatch",
            "--checkpoint",
            json.dumps(
                {
                    "path": "bad.pt",
                    "valid": True,
                    "contains": ["model", "optimizer"],
                    "identities": {**identity, "code": "different"},
                    "recorded_at": "now",
                }
            ),
        )
        self.run_cli(
            "observe",
            "attempt-mismatch",
            "--handle",
            '{"substrate":"local","host":"localhost","working_directory":"/tmp","command":"train","process_id":"123","log_location":"/tmp/train.log","wandb_run_id":null,"consumed_budget":{"cost":0,"wall_seconds":1},"status":"stopped","observed_at":"now"}',
        )
        self.assertEqual(self.output("next", "batch-1")["action"], "mark-interrupted")

    def test_interrupted_attempt_creates_linked_retry_action(self) -> None:
        identity = json.dumps(identities("retry"))
        self.run_cli("start", "batch-1", "exp-1", "attempt-old", "--identities", identity)
        self.run_cli(
            "finish",
            "attempt-old",
            "interrupted",
            "--result",
            json.dumps(result(False, "lost process")),
        )
        next_action = self.output("next", "batch-1")
        self.assertEqual(next_action["action"], "retry-experiment")
        self.assertEqual(next_action["previous_attempt_id"], "attempt-old")
        self.run_cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-new",
            "--parent-attempt-id",
            "attempt-old",
            "--identities",
            identity,
        )
        attempt = self.output("inspect", "attempt-new")
        self.assertEqual(attempt["experiment_id"], "exp-1")
        self.assertEqual(attempt["parent_attempt_id"], "attempt-old")

    def test_illegal_phase_transition_is_rejected_without_new_event(self) -> None:
        self.run_cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-invalid",
            "--identities",
            json.dumps(identities("invalid")),
        )
        before = (self.root / "ledger.jsonl").read_text(encoding="utf-8")
        completed = self.run_cli("transition", "attempt-invalid", "main-run", check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Illegal phase transition", completed.stderr)
        self.assertEqual(before, (self.root / "ledger.jsonl").read_text(encoding="utf-8"))

    def test_invalid_contract_is_rejected(self) -> None:
        other_root = self.base / "invalid-workflow"
        self.run_for_root(other_root, "init", "--title", "bad", "--mode", "existing")
        invalid = contract()
        invalid["approval"]["status"] = "pending"
        invalid_path = self.base / "invalid.json"
        invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
        completed = self.run_for_root(
            other_root, "register-batch", str(invalid_path), check=False
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("approval.status", completed.stderr)
        events = [
            json.loads(line)
            for line in (other_root / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual([event["event_type"] for event in events], ["project_initialized"])

    def run_for_root(
        self, root: Path, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(f"CLI failed: {completed.args}\n{completed.stdout}\n{completed.stderr}")
        return completed


if __name__ == "__main__":
    unittest.main()
