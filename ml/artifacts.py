"""Crash-safe single files and immutable, checksummed experiment generations."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4


@contextmanager
def atomic_path(destination: Path):
    """Keep the previous file intact until its replacement has finished writing."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, value) -> None:
    serialized = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with atomic_path(path) as temporary:
        temporary.write_text(serialized, encoding="utf-8")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def artifact_run(destination: Path):
    """Commit a generation before publishing its pointer; retain previous runs.

    Flat files remain compatibility copies. Readers using resolve_artifact follow the
    committed generation and verify its checksum, even if compatibility copying stops.
    """
    destination = Path(destination)
    runs = destination / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=runs))
    try:
        yield staging
        entries = list(staging.iterdir())
        if any(not path.is_file() for path in entries):
            raise RuntimeError("Experiment generations must contain only files.")
        for path in entries:
            with path.open("rb+") as stream:
                os.fsync(stream.fileno())
        files = {path.name: _digest(path) for path in entries}
        if not files:
            raise RuntimeError("Cannot publish an empty experiment.")
        write_json(
            staging / "manifest.json", {"format_version": 1, "run_id": run_id, "sha256": files}
        )
        committed = runs / run_id
        if (
            staging.resolve().parent != runs.resolve()
            or committed.resolve().parent != runs.resolve()
        ):
            raise RuntimeError("Artifact generation escaped its destination.")
        staging.rename(committed)
        write_json(destination / "latest.json", {"format_version": 1, "run_id": run_id})
        for name in [*files, "manifest.json"]:
            with atomic_path(destination / name) as temporary:
                shutil.copyfile(committed / name, temporary)
    finally:
        # Only the exact temporary directory created above is eligible for cleanup.
        if staging.exists() and staging.resolve().parent == runs.resolve():
            shutil.rmtree(staging)


def resolve_artifact(path: Path) -> Path:
    """Resolve a committed artifact and reject missing, altered or unsafe entries."""
    path = Path(path)
    pointer = path.parent / "latest.json"
    if not pointer.exists():
        return path  # Backward compatibility for existing trusted local artifacts.
    latest = json.loads(pointer.read_text(encoding="utf-8"))
    run_id = latest.get("run_id", "")
    if (
        latest.get("format_version") != 1
        or not isinstance(run_id, str)
        or not run_id
        or Path(run_id).name != run_id
        or "/" in run_id
        or "\\" in run_id
        or run_id in (".", "..")
    ):
        raise RuntimeError("Invalid artifact generation pointer.")
    root = path.parent / "runs" / run_id
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1 or manifest.get("run_id") != run_id:
        raise RuntimeError("Unsupported or mismatched artifact manifest.")
    expected = manifest.get("sha256", {}).get(path.name)
    resolved = root / path.name
    if not expected or not resolved.is_file() or _digest(resolved) != expected:
        raise RuntimeError(f"Artifact integrity check failed for {path.name}.")
    return resolved
