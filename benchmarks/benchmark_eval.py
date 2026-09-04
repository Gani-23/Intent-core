#!/usr/bin/env python3
"""Labeled benchmark evaluator for Intent Guard detection rules.

Runs a curated set of labeled agent sessions (clean/normal iterative development
vs. genuine drift/destructive sessions) through the full detection pipeline
and outputs empirical Precision, Recall, and F1 metrics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lsa.drift.models import ObservedEvent
from lsa.drift.mutation_rules import MutationComparator, SessionScope
from lsa.drift.session_ledger import LedgerEntry, analyze_ledger, _action_hash

@dataclass
class BenchmarkResult:
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return (self.true_positives / denom) if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return (self.true_positives / denom) if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) > 0 else 0.0


def run_benchmark(dataset_filename: str = "dataset.jsonl") -> BenchmarkResult:
    dataset_path = Path(__file__).parent / dataset_filename
    if not dataset_path.exists():
        raise FileNotFoundError(f"Benchmark dataset not found at {dataset_path}")

    tp = fp = tn = fn = 0
    comparator = MutationComparator()

    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        expected_drift = bool(case["expected_drift"])
        scope = SessionScope(task_text=case["task_text"])
        events = [ObservedEvent.from_dict(e) for e in case["events"]]

        # 1. Rule comparator
        alerts = comparator.compare(scope, events)
        
        # 2. Ledger analysis if ledger entries provided
        ledger_patterns = []
        if "ledger_entries" in case:
            entries = [LedgerEntry.from_dict(e) for e in case["ledger_entries"]]
            ledger_patterns = analyze_ledger(entries)

        flagged = bool(alerts or ledger_patterns)

        if expected_drift and flagged:
            tp += 1
        elif not expected_drift and flagged:
            fp += 1
        elif not expected_drift and not flagged:
            tn += 1
        elif expected_drift and not flagged:
            fn += 1

    return BenchmarkResult(tp, fp, tn, fn)


def print_metrics(name: str, res: BenchmarkResult) -> None:
    print(f"==================================================")
    print(f"EVALUATION: {name}")
    print(f"==================================================")
    total = res.true_positives + res.false_positives + res.true_negatives + res.false_negatives
    print(f"Total Evaluated Sessions  : {total}")
    print(f"True Positives (Caught)   : {res.true_positives}")
    print(f"True Negatives (Clean)    : {res.true_negatives}")
    print(f"False Positives (Spurious): {res.false_positives}")
    print(f"False Negatives (Missed)  : {res.false_negatives}")
    print(f"--------------------------------------------------")
    print(f"Precision : {res.precision:.1%}")
    print(f"Recall    : {res.recall:.1%}")
    print(f"F1 Score  : {res.f1:.1%}")
    print(f"==================================================\n")


if __name__ == "__main__":
    res_synth = run_benchmark("dataset.jsonl")
    print_metrics("Synthetic Regression Baseline (8 sessions)", res_synth)

    res_ext = run_benchmark("synthetic_dataset_v2.jsonl")
    print_metrics("Extended Synthetic Regression Set (10 sessions)", res_ext)
