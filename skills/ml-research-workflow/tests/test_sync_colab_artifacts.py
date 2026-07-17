from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = (
    Path(__file__).parents[1]
    / "run-colab-ml-experiments"
    / "scripts"
    / "sync_colab_artifacts.py"
)
SPEC = importlib.util.spec_from_file_location("sync_colab_artifacts", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SyncArtifactsTest(unittest.TestCase):
    def make_args(self, root: Path) -> argparse.Namespace:
        return argparse.Namespace(
            artifact=[
                MODULE.Artifact("/content/checkpoint.pt", root / "checkpoint.pt")
            ],
            auth=None,
            colab_bin="colab",
            config=None,
            manifest=str(root / "manifest.jsonl"),
            session="attempt-1",
        )

    def test_parse_artifact_rejects_paths_outside_content(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            MODULE.parse_artifact("/tmp/checkpoint.pt=checkpoint.pt")

    def test_successful_sync_atomically_replaces_and_records_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.make_args(root)
            destination = args.artifact[0].local
            destination.write_bytes(b"old")

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"new-checkpoint")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(MODULE.subprocess, "run", side_effect=fake_run):
                self.assertEqual(MODULE.run_once(args), 0)

            self.assertEqual(destination.read_bytes(), b"new-checkpoint")
            event = json.loads((root / "manifest.jsonl").read_text().strip())
            self.assertEqual(event["status"], "updated")
            self.assertEqual(event["size"], len(b"new-checkpoint"))
            self.assertEqual(len(event["sha256"]), 64)

    def test_failed_sync_preserves_last_verified_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.make_args(root)
            destination = args.artifact[0].local
            destination.write_bytes(b"verified")

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"partial")
                return subprocess.CompletedProcess(command, 1, "", "failure")

            with mock.patch.object(MODULE.subprocess, "run", side_effect=fake_run):
                self.assertEqual(MODULE.run_once(args), 2)

            self.assertEqual(destination.read_bytes(), b"verified")
            event = json.loads((root / "manifest.jsonl").read_text().strip())
            self.assertEqual(event["status"], "failed")

    def test_download_command_places_global_options_before_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.make_args(root)
            args.auth = "adc"
            args.config = root / "sessions.json"
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                Path(command[-1]).write_bytes(b"checkpoint")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(MODULE.subprocess, "run", side_effect=fake_run):
                self.assertEqual(MODULE.run_once(args), 0)

            self.assertEqual(
                commands[0][:5],
                ["colab", "--auth=adc", "--config", str(args.config), "download"],
            )

    def test_watcher_requires_final_sync_after_completion_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.make_args(root)
            args.completion_remote = "/content/attempt.complete"
            args.interval_seconds = 120.0
            args.max_seconds = 3600.0

            with (
                mock.patch.object(MODULE, "sync_all", side_effect=[True, True]) as sync,
                mock.patch.object(MODULE, "completion_visible", return_value=True),
            ):
                self.assertEqual(MODULE.run_watch(args), 0)

            self.assertEqual(sync.call_count, 2)


if __name__ == "__main__":
    unittest.main()
