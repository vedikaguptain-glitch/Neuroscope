"""Failure-path tests for CLI, artifacts, records and database boundaries."""

import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import main
from ml.artifacts import artifact_run, atomic_path, resolve_artifact, write_json
from ml.config import validate_cv
from ml.records import validate_sessions
from test_ml_pipeline import session


class ArtifactTests(unittest.TestCase):
    def test_interrupted_single_write_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            path.write_bytes(b"previous")
            with self.assertRaises(RuntimeError):
                with atomic_path(path) as temporary:
                    temporary.write_bytes(b"partial")
                    raise RuntimeError("interrupted")
            self.assertEqual(path.read_bytes(), b"previous")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_generations_retain_previous_and_detect_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for n in (1, 2):
                with artifact_run(root) as stage:
                    write_json(stage / "results.json", {"n": n})
            self.assertEqual(len(list((root / "runs").iterdir())), 2)
            committed = resolve_artifact(root / "results.json")
            self.assertEqual(json.loads(committed.read_text()), {"n": 2})
            (root / "results.json").write_text("stale compatibility copy")
            self.assertEqual(resolve_artifact(root / "results.json"), committed)
            committed.write_text("corrupt")
            with self.assertRaisesRegex(RuntimeError, "integrity"):
                resolve_artifact(root / "results.json")

    def test_failed_generation_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with artifact_run(root) as stage:
                write_json(stage / "results.json", {"n": 1})
            pointer = (root / "latest.json").read_bytes()
            with self.assertRaises(ValueError):
                with artifact_run(root) as stage:
                    write_json(stage / "results.json", {"n": float("nan")})
            self.assertEqual((root / "latest.json").read_bytes(), pointer)
            self.assertEqual(len(list((root / "runs").iterdir())), 1)

    def test_unsafe_generation_pointer_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "latest.json", {"format_version": 1, "run_id": "../elsewhere"})
            with self.assertRaisesRegex(RuntimeError, "pointer"):
                resolve_artifact(root / "predictor.joblib")


class BoundaryTests(unittest.TestCase):
    def test_help_needs_no_installed_third_party_packages(self):
        result = subprocess.run(
            [sys.executable, "-S", "main.py", "--help"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--seed", result.stdout)

    def test_invalid_options_fail_before_execution(self):
        for args in (
            ["--train", "--epochs", "0"],
            ["--train", "--lr", "nan"],
            ["--evaluate", "--outer-folds", "1"],
            ["--conditional-risk", "--held-out-task", "delay_disc"],
        ):
            with (
                self.subTest(args=args),
                patch("main._run") as execute,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as error:
                    main.main(args)
                self.assertEqual(error.exception.code, 2)
                execute.assert_not_called()

    def test_offline_modules_do_not_import_torch_or_database(self):
        command = "import sys; import ml.utils.optimize; import ml.utils.conditional_policy; assert 'torch' not in sys.modules; assert 'psycopg2' not in sys.modules"
        result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_custom_paths_and_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps([session(0), session(1)]))
            with patch("ml.utils.optimize.run_optimization") as optimize:
                self.assertEqual(
                    main.main(
                        [
                            "--evaluate",
                            "--input",
                            str(source),
                            "--output-dir",
                            str(root),
                            "--seed",
                            "7",
                        ]
                    ),
                    0,
                )
                self.assertEqual(optimize.call_args.kwargs["seed"], 7)
                self.assertEqual(optimize.call_args.kwargs["output_dir"].parent, root)

    def test_corrupt_records_are_rejected(self):
        original = session()
        variants = []
        duplicate = copy.deepcopy(original)
        duplicate["trials"].append(copy.deepcopy(duplicate["trials"][0]))
        variants.append(duplicate)
        for field, value in (
            ("reaction_time_ms", float("nan")),
            ("task_id", []),
            ("trial_index", 0),
        ):
            item = copy.deepcopy(original)
            item["trials"][0][field] = value
            variants.append(item)
        for invalid in variants:
            with self.assertRaises(ValueError):
                validate_sessions([invalid])

    def test_cv_rejects_insufficient_inner_classes(self):
        with self.assertRaisesRegex(RuntimeError, "inner"):
            validate_cv([0] * 3 + [1] * 3, 3, 3, 1)

    def test_database_is_bounded_read_only_and_closed(self):
        from ml.utils.db import connect

        connection = MagicMock()
        with (
            patch(
                "ml.utils.db.load_database_url", return_value="postgresql://example.invalid/test"
            ),
            patch("ml.utils.db.psycopg2.connect", return_value=connection) as create,
        ):
            with connect() as actual:
                self.assertIs(actual, connection)
            self.assertEqual(create.call_args.kwargs["connect_timeout"], 10)
            connection.set_session.assert_called_once_with(readonly=True)
            connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
