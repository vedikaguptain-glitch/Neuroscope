"""NEUROSCOPE machine learning pipeline entry point."""

from __future__ import annotations

import argparse
import json
import sys

import math
from pathlib import Path
from ml.config import TASK_ORDER


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
        "--optimize",
        action="store_true",
        help="Select cross-task predictors using nested participant cross-validation.",
    )
    parser.add_argument(
        "--probe", action="store_true", help="Run the exploratory pretrained-embedding diagnostic."
    )
    parser.add_argument(
        "--conditional-risk",
        action="store_true",
        help="Predict risk choices given offered gambles and other-task behavior using nested participant validation.",
    )
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs (with --train).")
    parser.add_argument("--outer-folds", type=int, default=5)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=4, help="Parallel model-selection workers.")
    parser.add_argument(
        "--search-profile",
        choices=["summary", "behavioral"],
        default="summary",
        help="Summary predictors (40 configurations) or experimental behavioral weights (94).",
    )
    parser.add_argument("--batch-size", type=int, default=4, help="Mini-batch size (with --train).")
    parser.add_argument(
        "--lr", type=float, default=3e-4, help="AdamW learning rate (with --train)."
    )
    parser.add_argument(
        "--held-out-task",
        default="risk_pref",
        choices=list(TASK_ORDER),
        help="Task predicted from the other four (with --evaluate or --optimize).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Advanced nested risk benchmark with richer features and optional training-only auxiliary data.",
    )
    parser.add_argument(
        "--rate-benchmark",
        action="store_true",
        help="Use continuous gamble-rate supervision with the same binary held-out target.",
    )
    parser.add_argument(
        "--covariate-benchmark",
        action="store_true",
        help="Compare age/class, behavior, and combined inputs in nested risk prediction.",
    )
    parser.add_argument(
        "--auxiliary-input",
        type=Path,
        help="Risk-complete sessions; evaluation participants are removed before training augmentation.",
    )
    parser.add_argument("--inner-repeats", type=int, default=2)
    parser.add_argument("--input", type=Path, help="Participant JSON for offline stages.")
    parser.add_argument("--output-dir", type=Path, help="Root for new experiment artifacts.")
    args = parser.parse_args(argv)
    for name in ("epochs", "batch_size", "jobs"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.outer_folds < 2 or args.inner_folds < 2:
        parser.error("cross-validation requires at least two outer and inner folds")
    if args.inner_repeats < 1:
        parser.error("--inner-repeats must be positive")
    if (
        args.benchmark or args.rate_benchmark or args.covariate_benchmark
    ) and args.held_out_task != "risk_pref":
        parser.error("--benchmark currently evaluates the unchanged risk_pref target")
    if args.auxiliary_input and not (args.benchmark or args.rate_benchmark):
        parser.error("--auxiliary-input applies to --benchmark or --rate-benchmark")
    if not math.isfinite(args.lr) or args.lr <= 0:
        parser.error("--lr must be finite and positive")
    if not 0 <= args.seed < 2**32:
        parser.error("--seed must be between 0 and 2**32 - 1")
    if args.evaluate and args.held_out_task not in ("risk_pref", "delay_disc", "social_ultimatum"):
        parser.error(
            "--evaluate supports risk_pref, delay_disc and social_ultimatum; use --probe for other tasks"
        )
    if args.conditional_risk and args.held_out_task != "risk_pref":
        parser.error("--conditional-risk requires --held-out-task risk_pref")
    return args


def _run(args: argparse.Namespace) -> int:
    from ml.records import load_raw_participants

    source = args.input
    output = args.output_dir
    checkpoint = output / "models" / "neuroscope_msm.pt" if output else None

    if not (
        args.extract
        or args.train
        or args.evaluate
        or args.probe
        or args.conditional_risk
        or args.benchmark
        or args.rate_benchmark
        or args.covariate_benchmark
    ):
        print(
            "Specify at least one of --extract, --train, --evaluate, --probe, or --conditional-risk.",
            file=sys.stderr,
        )
        return 2

    if args.extract:
        from ml.utils.extract import extract_completed_sessions
        from ml.utils.preprocess import preprocess_raw_participants

        try:
            output_path = extract_completed_sessions(
                output / "raw_participants.json" if output else None
            )
            source = output_path
        except RuntimeError as exc:
            print(f"[extract] {exc}", file=sys.stderr)
            return 1
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        n_sessions = len(payload) if isinstance(payload, list) else 0
        print(f"[extract] wrote {n_sessions} completed session(s) to {output_path}")
        try:
            bundle = preprocess_raw_participants(output_path, output_dir=output)
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
        from ml.utils.train import run_training

        try:
            checkpoint = run_training(
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                seed=args.seed,
                raw_path=source,
                checkpoint_path=checkpoint,
            )
        except RuntimeError as exc:
            print(f"[train] {exc}", file=sys.stderr)
            return 1
        print(f"[train] checkpoint={checkpoint}")
    if args.probe:
        from ml.utils.evaluate import run_evaluation

        try:
            run_evaluation(
                held_out_task=args.held_out_task,
                seed=args.seed,
                raw_path=source,
                checkpoint_path=checkpoint,
            )
        except RuntimeError as exc:
            print(f"[evaluate] {exc}", file=sys.stderr)
            return 1

    if args.evaluate:
        from ml.utils.optimize import run_optimization

        try:
            run_optimization(
                held_out_task=args.held_out_task,
                outer_folds=args.outer_folds,
                inner_folds=args.inner_folds,
                jobs=args.jobs,
                profile=args.search_profile,
                seed=args.seed,
                sessions=load_raw_participants(source),
                output_dir=output / f"optimization_{args.held_out_task}_{args.search_profile}"
                if output
                else None,
            )
        except RuntimeError as exc:
            print(f"[optimize] {exc}", file=sys.stderr)
            return 1

    if args.conditional_risk:
        from ml.utils.conditional_policy import run_conditional_policy

        if args.held_out_task != "risk_pref":
            print(
                "[conditional] --conditional-risk requires --held-out-task risk_pref.",
                file=sys.stderr,
            )
            return 1
        run_conditional_policy(
            outer_folds=args.outer_folds,
            inner_folds=args.inner_folds,
            jobs=args.jobs,
            seed=args.seed,
            sessions=load_raw_participants(source),
            output_dir=output / "conditional_risk_policy" if output else None,
        )

    if args.benchmark:
        from ml.utils.advanced_benchmark import run_advanced_benchmark

        run_advanced_benchmark(
            sessions=load_raw_participants(source),
            auxiliary_sessions=load_raw_participants(args.auxiliary_input)
            if args.auxiliary_input
            else None,
            output_dir=output / "optimization_advanced_risk_pref" if output else None,
            seed=args.seed,
            outer_folds=args.outer_folds,
            inner_folds=args.inner_folds,
            repeats=args.inner_repeats,
            jobs=args.jobs,
        )

    if args.rate_benchmark:
        from ml.utils.rate_benchmark import run_rate_benchmark

        run_rate_benchmark(
            sessions=load_raw_participants(source),
            auxiliary_sessions=load_raw_participants(args.auxiliary_input)
            if args.auxiliary_input
            else None,
            output_dir=output / "optimization_risk_rate" if output else None,
            seed=args.seed,
            outer_folds=args.outer_folds,
            inner_folds=args.inner_folds,
            repeats=args.inner_repeats,
            jobs=args.jobs,
        )

    if args.covariate_benchmark:
        from ml.utils.covariate_benchmark import run_covariate_benchmark

        run_covariate_benchmark(
            sessions=load_raw_participants(source),
            output_dir=output / "optimization_covariate_risk" if output else None,
            seed=args.seed,
            outer_folds=args.outer_folds,
            inner_folds=args.inner_folds,
            jobs=args.jobs,
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return _run(args)
    except KeyboardInterrupt:
        print("[pipeline] interrupted", file=sys.stderr)
        return 130
    except (RuntimeError, ValueError, OSError, ImportError) as exc:
        print(f"[pipeline] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
