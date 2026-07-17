from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_ml_ledger import SCRIPT, contract


IDENTITIES = {"code": "c1", "data": "d1", "config": "cfg1", "environment": "env1"}


class LedgerRemediationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "ml-workflow"
        self.contract_path = self.base / "contract.json"
        planned = contract()
        planned["budget"] = {"max_runs": 5, "max_cost": 10.0, "max_wall_seconds": 100.0}
        self.contract_path.write_text(json.dumps(planned), encoding="utf-8")
        self.cli("init", "--title", "fixture", "--mode", "greenfield")
        self.cli("register-batch", str(self.contract_path))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
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
        return json.loads(self.cli(*args).stdout)

    def start_and_reach_main(self, attempt_id: str = "attempt-1") -> None:
        self.cli(
            "start",
            "batch-1",
            "exp-1",
            attempt_id,
            "--identities",
            json.dumps(IDENTITIES),
        )
        for phase in (
            "implementing",
            "preflight",
            "fit-one-batch",
            "smoke",
            "snapshot",
            "main-run",
        ):
            self.cli("transition", attempt_id, phase)

    def test_stopped_mismatched_checkpoint_requires_interruption(self) -> None:
        self.start_and_reach_main()
        self.cli(
            "observe",
            "attempt-1",
            "--handle",
            json.dumps(
                {
                    "substrate": "local",
                    "host": "localhost",
                    "working_directory": "/tmp",
                    "command": "train",
                    "process_id": "123",
                    "log_location": "/tmp/train.log",
                    "wandb_run_id": None,
                    "consumed_budget": {"cost": 1.0, "wall_seconds": 10.0},
                    "status": "stopped",
                    "observed_at": "now",
                }
            ),
        )
        self.cli(
            "checkpoint",
            "attempt-1",
            "--checkpoint",
            json.dumps(
                {
                    "path": "bad.pt",
                    "valid": True,
                    "contains": ["model", "optimizer"],
                    "identities": {**IDENTITIES, "code": "other"},
                    "recorded_at": "now",
                }
            ),
        )
        self.assertEqual(self.output("next", "batch-1")["action"], "mark-interrupted")

    def test_retry_parent_is_persisted(self) -> None:
        result = {
            "valid": False,
            "metrics": {},
            "cost": {"cost": 0.0, "wall_seconds": 1.0},
            "artifacts": [],
            "wandb": {"mode": "unavailable", "run_id": None, "url": None},
            "conclusion": "process stopped",
        }
        self.cli("start", "batch-1", "exp-1", "attempt-old", "--identities", json.dumps(IDENTITIES))
        self.cli("finish", "attempt-old", "interrupted", "--result", json.dumps(result))
        self.cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-new",
            "--parent-attempt-id",
            "attempt-old",
            "--identities",
            json.dumps(IDENTITIES),
        )
        self.assertEqual(self.output("inspect", "attempt-new")["parent_attempt_id"], "attempt-old")

    def test_budget_is_projected_and_blocks_exhaustion(self) -> None:
        self.start_and_reach_main()
        self.cli(
            "budget",
            "attempt-1",
            "--consumed",
            '{"cost":10.0,"wall_seconds":20.0}',
        )
        status = self.output("status", "--batch-id", "batch-1")
        self.assertEqual(status["budget"]["remaining"]["max_cost"], 0.0)
        self.assertEqual(status["next_action"]["action"], "blocked")
        self.assertEqual(status["next_action"]["reason"], "budget-exhausted")

    def test_torn_final_ledger_line_recovers_valid_prefix(self) -> None:
        ledger = self.root / "ledger.jsonl"
        with ledger.open("ab") as handle:
            handle.write(b'{"event_type":"attempt_started"')
        rebuilt = self.output("rebuild")
        self.assertIn("batch-1", rebuilt["batches"])
        self.assertTrue(ledger.read_bytes().endswith(b"\n"))

    def test_empty_checkpoint_identities_are_rejected(self) -> None:
        completed = self.cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-empty",
            "--identities",
            "{}",
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("identities.code", completed.stderr)

    def test_projection_disagreement_and_missing_run_projection_are_rebuilt(self) -> None:
        self.cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-projection",
            "--identities",
            json.dumps(IDENTITIES),
        )
        batch_state = self.root / "batches" / "batch-1" / "state.json"
        batch_state.write_text('{"wrong":true}\n', encoding="utf-8")
        run_state = self.root / "runs" / "attempt-projection" / "state.json"
        run_state.unlink()
        rebuilt = self.output("rebuild")
        self.assertEqual(
            json.loads(batch_state.read_text(encoding="utf-8"))["batch_id"], "batch-1"
        )
        self.assertTrue(run_state.exists())
        self.assertEqual(rebuilt["attempts"]["attempt-projection"]["phase"], "planned")

    def test_evaluation_only_path_skips_fit_one_batch(self) -> None:
        other_root = self.base / "eval-workflow"
        planned = contract(max_runs=1)
        planned["batch_id"] = "eval-batch"
        planned["experiments"] = [
            {
                "experiment_id": "eval-1",
                "hypothesis": "evaluation remains valid",
                "kind": "evaluation-only",
                "parent_id": "baseline",
                "config": {},
                "depends_on": [],
                "retry": {"max_attempts": 1},
            }
        ]
        path = self.base / "eval-contract.json"
        path.write_text(json.dumps(planned), encoding="utf-8")
        self.cli_for(other_root, "init", "--title", "eval", "--mode", "existing")
        self.cli_for(other_root, "register-batch", str(path))
        self.cli_for(
            other_root,
            "start",
            "eval-batch",
            "eval-1",
            "eval-attempt",
            "--identities",
            json.dumps(IDENTITIES),
        )
        self.cli_for(other_root, "transition", "eval-attempt", "implementing")
        self.cli_for(other_root, "transition", "eval-attempt", "preflight")
        rejected = self.cli_for(
            other_root, "transition", "eval-attempt", "fit-one-batch", check=False
        )
        self.assertEqual(rejected.returncode, 2)
        self.cli_for(other_root, "transition", "eval-attempt", "smoke")

    def test_all_noncompleted_terminal_states_are_preserved(self) -> None:
        for status in ("failed", "interrupted", "cancelled", "invalid"):
            with self.subTest(status=status):
                root = self.base / f"terminal-{status}"
                planned = contract(max_runs=1)
                planned["batch_id"] = f"batch-{status}"
                planned["experiments"] = [planned["experiments"][0]]
                path = self.base / f"contract-{status}.json"
                path.write_text(json.dumps(planned), encoding="utf-8")
                self.cli_for(root, "init", "--title", status, "--mode", "existing")
                self.cli_for(root, "register-batch", str(path))
                self.cli_for(
                    root,
                    "start",
                    f"batch-{status}",
                    "exp-1",
                    f"attempt-{status}",
                    "--identities",
                    json.dumps(IDENTITIES),
                )
                final = {
                    "valid": False,
                    "metrics": {},
                    "cost": {"cost": 0.0, "wall_seconds": 1.0},
                    "artifacts": [],
                    "wandb": {"mode": "unavailable", "run_id": None, "url": None},
                    "conclusion": status,
                }
                self.cli_for(
                    root,
                    "finish",
                    f"attempt-{status}",
                    status,
                    "--result",
                    json.dumps(final),
                )
                inspected = json.loads(
                    self.cli_for(root, "inspect", f"attempt-{status}").stdout
                )
                self.assertEqual(inspected["status"], status)

    def test_orphan_contract_is_recovered_from_authoritative_event(self) -> None:
        root = self.base / "orphan-workflow"
        self.cli_for(root, "init", "--title", "orphan", "--mode", "greenfield")
        orphan = root / "batches" / "batch-1" / "contract.json"
        orphan.parent.mkdir(parents=True)
        orphan.write_text('{"partial":true}\n', encoding="utf-8")
        self.cli_for(root, "register-batch", str(self.contract_path))
        self.assertEqual(json.loads(orphan.read_text(encoding="utf-8"))["batch_id"], "batch-1")

    def test_project_projection_tracks_active_batch(self) -> None:
        project = (self.root / "project.md").read_text(encoding="utf-8")
        self.assertIn("Active batch: batch-1", project)
        self.assertIn("Next action: start-experiment", project)

    def test_budget_exhaustion_blocks_transition_and_cost_rollback(self) -> None:
        self.cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-budget-gate",
            "--identities",
            json.dumps(IDENTITIES),
        )
        for phase in ("implementing", "preflight", "fit-one-batch", "smoke"):
            self.cli("transition", "attempt-budget-gate", phase)
        self.cli(
            "budget",
            "attempt-budget-gate",
            "--consumed",
            '{"cost":10.0,"wall_seconds":20.0}',
        )
        blocked = self.cli(
            "transition", "attempt-budget-gate", "snapshot", check=False
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("budget is exhausted", blocked.stderr)
        rollback = {
            "valid": False,
            "metrics": {},
            "cost": {"cost": 1.0, "wall_seconds": 2.0},
            "artifacts": [],
            "wandb": {"mode": "unavailable", "run_id": None, "url": None},
            "conclusion": "stopped at budget",
        }
        rejected = self.cli(
            "finish",
            "attempt-budget-gate",
            "interrupted",
            "--result",
            json.dumps(rollback),
            check=False,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("cannot decrease", rejected.stderr)

    def test_second_batch_is_rejected_while_first_is_active(self) -> None:
        self.cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-active",
            "--identities",
            json.dumps(IDENTITIES),
        )
        second = contract()
        second["batch_id"] = "batch-2"
        second_path = self.base / "second-contract.json"
        second_path.write_text(json.dumps(second), encoding="utf-8")
        rejected = self.cli("register-batch", str(second_path), check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("active batch", rejected.stderr)

    def test_project_rebuild_is_deterministic_and_includes_decisions_and_budget(self) -> None:
        self.cli(
            "update-project",
            "--changes",
            '{"decision_state":{"approved_direction":"baseline first"}}',
        )
        before = (self.root / "project.md").read_bytes()
        self.output("rebuild")
        after = (self.root / "project.md").read_bytes()
        self.assertEqual(before, after)
        project = after.decode("utf-8")
        self.assertIn("approved_direction", project)
        self.assertIn("max_cost", project)

    def test_logical_parent_is_required_and_projected(self) -> None:
        status = self.output("status", "--batch-id", "batch-1")
        self.assertEqual(status["experiments"]["exp-1"]["parent_id"], "baseline")
        other_root = self.base / "missing-parent"
        planned = contract()
        del planned["experiments"][0]["parent_id"]
        invalid_path = self.base / "missing-parent.json"
        invalid_path.write_text(json.dumps(planned), encoding="utf-8")
        self.cli_for(other_root, "init", "--title", "bad parent", "--mode", "greenfield")
        rejected = self.cli_for(
            other_root, "register-batch", str(invalid_path), check=False
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("parent_id", rejected.stderr)

    def test_execution_observation_budget_cannot_decrease(self) -> None:
        self.cli(
            "start",
            "batch-1",
            "exp-1",
            "attempt-observe",
            "--identities",
            json.dumps(IDENTITIES),
        )
        base_handle = {
            "substrate": "local",
            "host": "localhost",
            "working_directory": "/tmp",
            "command": "train",
            "process_id": "321",
            "log_location": "/tmp/train.log",
            "wandb_run_id": None,
            "status": "running",
            "observed_at": "now",
        }
        self.cli(
            "observe",
            "attempt-observe",
            "--handle",
            json.dumps(
                {**base_handle, "consumed_budget": {"cost": 10.0, "wall_seconds": 20.0}}
            ),
        )
        rejected = self.cli(
            "observe",
            "attempt-observe",
            "--handle",
            json.dumps(
                {**base_handle, "consumed_budget": {"cost": 1.0, "wall_seconds": 5.0}}
            ),
            check=False,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("cannot decrease", rejected.stderr)

    def test_terminal_blocked_batch_can_close_before_next_batch(self) -> None:
        root = self.base / "sequential-workflow"
        first = contract(max_runs=1)
        first["batch_id"] = "first-batch"
        first["experiments"] = [first["experiments"][0]]
        first["experiments"][0]["retry"]["max_attempts"] = 1
        first_path = self.base / "first-contract.json"
        first_path.write_text(json.dumps(first), encoding="utf-8")
        self.cli_for(root, "init", "--title", "sequential", "--mode", "existing")
        self.cli_for(root, "register-batch", str(first_path))
        self.cli_for(
            root,
            "start",
            "first-batch",
            "exp-1",
            "failed-attempt",
            "--identities",
            json.dumps(IDENTITIES),
        )
        failed_result = {
            "valid": False,
            "metrics": {},
            "cost": {"cost": 0.0, "wall_seconds": 1.0},
            "artifacts": [],
            "wandb": {"mode": "unavailable", "run_id": None, "url": None},
            "conclusion": "failed",
        }
        self.cli_for(
            root,
            "finish",
            "failed-attempt",
            "failed",
            "--result",
            json.dumps(failed_result),
        )
        self.cli_for(
            root,
            "close-batch",
            "first-batch",
            "--reason",
            "terminal failed batch reviewed",
        )
        second = contract()
        second["batch_id"] = "second-batch"
        second_path = self.base / "sequential-second.json"
        second_path.write_text(json.dumps(second), encoding="utf-8")
        self.cli_for(root, "register-batch", str(second_path))
        state = json.loads(self.cli_for(root, "status", "--batch-id", "first-batch").stdout)
        self.assertEqual(state["next_action"]["action"], "batch-closed")

    def test_project_update_rejects_unknown_active_batch(self) -> None:
        rejected = self.cli(
            "update-project",
            "--changes",
            '{"active_batch_id":"missing-batch"}',
            check=False,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("Unknown active_batch_id", rejected.stderr)

    def cli_for(
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
