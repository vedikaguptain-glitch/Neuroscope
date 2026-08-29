"""NEUROSCOPE machine learning pipeline entry point."""

from __future__ import annotations

import argparse
import json
import sys

import psycopg2

from ml.utils.evaluate import run_evaluation
from ml.utils.extract import extract_completed_sessions
from ml.utils.preprocess import preprocess_raw_participants, TASK_ORDER
from ml.utils.train import run_training


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "NEUROSCOPE self-supervised pipeline: extract completed sessions, "
            "train a behavioral transformer, and evaluate held-out generalization."
        )
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Download fully completed 240-trial experiments from PostgreSQL.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Train the transformer on extracted behavioral sequences.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run linear probing on frozen embeddings for a held-out task.",
    )
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs (with --train).")
    parser.add_argument("--batch-size", type=int, default=4, help="Mini-batch size (with --train).")
    parser.add_argument("--lr", type=float, default=3e-4, help="AdamW learning rate (with --train).")
    parser.add_argument(
        "--held-out-task",
        default="risk_pref",
        choices=list(TASK_ORDER),
        help="Task whose behavior is predicted from the other four tasks (with --evaluate).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not (args.extract or args.train or args.evaluate):
        print(
            "Specify at least one of --extract, --train, or --evaluate.",
            file=sys.stderr,
        )
        return 2

    if args.extract:
        try:
            output_path = extract_completed_sessions()
        except (RuntimeError, psycopg2.Error) as exc:
            print(f"[extract] {exc}", file=sys.stderr)
            return 1
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        n_sessions = len(payload) if isinstance(payload, list) else 0
        print(f"[extract] wrote {n_sessions} completed session(s) to {output_path}")
        try:
            bundle = preprocess_raw_participants(output_path)
        except RuntimeError as exc:
            print(f"[preprocess] {exc}", file=sys.stderr)
            return 1
        x = bundle["x"]
        spec = bundle["spec"]
        print(
            "[preprocess] "
            f"{len(bundle['participant_ids'])} sequence(s) "
            f"x_t shape={tuple(x.shape)} "
            f"action_vocab={len(spec['action_vocab'])} "
            f"task_vocab={len(spec['task_vocab'])}"
        )
    if args.train:
        try:
            checkpoint = run_training(
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
            )
        except RuntimeError as exc:
            print(f"[train] {exc}", file=sys.stderr)
            return 1
        print(f"[train] checkpoint={checkpoint}")
    if args.evaluate:
        try:
            run_evaluation(held_out_task=args.held_out_task)
        except RuntimeError as exc:
            print(f"[evaluate] {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
