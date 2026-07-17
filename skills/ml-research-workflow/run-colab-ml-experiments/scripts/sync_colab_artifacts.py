#!/usr/bin/env python3
"""Atomically mirror files from a named Colab CLI session."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence


@dataclass(frozen=True)
class Artifact:
    remote: str
    local: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_artifact(value: str) -> Artifact:
    if "=" not in value:
        raise argparse.ArgumentTypeError("artifact must be REMOTE=LOCAL")
    remote, local = value.split("=", 1)
    if not remote.startswith("/content/"):
        raise argparse.ArgumentTypeError("remote artifact must be under /content/")
    if not local:
        raise argparse.ArgumentTypeError("local artifact path cannot be empty")
    return Artifact(remote=remote, local=Path(local).expanduser().resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_manifest(manifest: Path, event: dict[str, object]) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


def colab_prefix(args: argparse.Namespace) -> list[str]:
    command = [args.colab_bin]
    if args.auth:
        command.append(f"--auth={args.auth}")
    if args.config:
        command.extend(["--config", str(Path(args.config).expanduser())])
    return command


def download_atomic(
    args: argparse.Namespace,
    artifact: Artifact,
    manifest: Path,
    *,
    event_type: str = "artifact_sync",
) -> bool:
    artifact.local.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{artifact.local.name}.colab-",
        dir=artifact.local.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()

    command = colab_prefix(args) + [
        "download",
        "-s",
        args.session,
        artifact.remote,
        str(temporary),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        append_manifest(
            manifest,
            {
                "event": event_type,
                "local": str(artifact.local),
                "remote": artifact.remote,
                "returncode": result.returncode,
                "session": args.session,
                "status": "failed",
                "timestamp": utc_now(),
            },
        )
        return False

    size = temporary.stat().st_size
    digest = sha256_file(temporary)
    unchanged = (
        artifact.local.is_file()
        and artifact.local.stat().st_size == size
        and sha256_file(artifact.local) == digest
    )
    os.replace(temporary, artifact.local)
    append_manifest(
        manifest,
        {
            "event": event_type,
            "local": str(artifact.local),
            "remote": artifact.remote,
            "session": args.session,
            "sha256": digest,
            "size": size,
            "status": "unchanged" if unchanged else "updated",
            "timestamp": utc_now(),
        },
    )
    return True


def sync_all(args: argparse.Namespace, manifest: Path) -> bool:
    results = [download_atomic(args, artifact, manifest) for artifact in args.artifact]
    return all(results)


def completion_visible(args: argparse.Namespace, manifest: Path) -> bool:
    destination = manifest.parent / f".{args.session}.completion-sentinel"
    artifact = Artifact(args.completion_remote, destination)
    visible = download_atomic(
        args,
        artifact,
        manifest,
        event_type="completion_probe",
    )
    destination.unlink(missing_ok=True)
    return visible


def run_once(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest).expanduser().resolve()
    return 0 if sync_all(args, manifest) else 2


def run_watch(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest).expanduser().resolve()
    started = time.monotonic()
    try:
        while True:
            sync_all(args, manifest)
            if completion_visible(args, manifest):
                return 0 if sync_all(args, manifest) else 2
            elapsed = time.monotonic() - started
            if elapsed >= args.max_seconds:
                sync_all(args, manifest)
                return 3
            time.sleep(min(args.interval_seconds, args.max_seconds - elapsed))
    except KeyboardInterrupt:
        sync_all(args, manifest)
        return 130


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session", required=True, help="Named Colab CLI session")
    parser.add_argument(
        "--artifact",
        action="append",
        required=True,
        type=parse_artifact,
        help="Required file mapping REMOTE=LOCAL; repeat for each artifact",
    )
    parser.add_argument(
        "--manifest", required=True, help="Append-only local JSONL manifest"
    )
    parser.add_argument("--colab-bin", default="colab", help="Colab CLI executable")
    parser.add_argument("--auth", choices=("oauth2", "adc"), help="Colab auth provider")
    parser.add_argument("--config", help="Colab CLI session-state file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mirror required files from a Colab session without mounting Drive. "
            "This tool never stops the remote session."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    once = subparsers.add_parser("once", help="Download every required artifact once")
    add_common_arguments(once)
    once.set_defaults(func=run_once)

    watch = subparsers.add_parser(
        "watch",
        help="Periodically mirror artifacts until a completion sentinel appears",
    )
    add_common_arguments(watch)
    watch.add_argument(
        "--completion-remote",
        required=True,
        type=lambda value: parse_artifact(f"{value}=sentinel").remote,
        help="Remote /content file written only after successful completion",
    )
    watch.add_argument("--interval-seconds", type=float, default=120.0)
    watch.add_argument("--max-seconds", type=float, required=True)
    watch.set_defaults(func=run_watch)
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    destinations = [artifact.local for artifact in args.artifact]
    if len(destinations) != len(set(destinations)):
        parser.error("local artifact destinations must be unique")
    if args.mode == "watch":
        if args.interval_seconds <= 0:
            parser.error("--interval-seconds must be positive")
        if args.max_seconds <= 0:
            parser.error("--max-seconds must be positive")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
