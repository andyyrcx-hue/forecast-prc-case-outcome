#!/usr/bin/env python3
"""Calculate transparent PRC case-similarity scores from reviewer-supplied ratings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WEIGHTS = {
    "issue": 0.25,
    "decisive_facts": 0.25,
    "legal_relation": 0.15,
    "applied_law": 0.15,
    "evidence_structure": 0.10,
    "procedural_posture": 0.05,
    "temporal_context": 0.05,
}


def validate_rating(value: object, field: str, case_id: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{case_id}: {field} must be a number from 0 to 100")
    number = float(value)
    if not 0 <= number <= 100:
        raise ValueError(f"{case_id}: {field} must be between 0 and 100")
    return number


def band(score: float, ratings: dict[str, float]) -> str:
    if ratings["legal_relation"] < 40 or ratings["issue"] < 40:
        return "exclude"
    if ratings["decisive_facts"] < 40:
        return "rule-reference-only"
    if score >= 85:
        return "highly-similar"
    if score >= 70:
        return "substantially-similar"
    if score >= 55:
        return "partly-similar"
    if score >= 40:
        return "rule-reference-only"
    return "exclude"


def score_case(item: object, index: int) -> dict[str, object]:
    if not isinstance(item, dict):
        raise ValueError(f"item {index} must be an object")
    case_id = str(item.get("case_id") or item.get("citation") or f"item-{index}")
    ratings_raw = item.get("ratings")
    if not isinstance(ratings_raw, dict):
        raise ValueError(f"{case_id}: ratings must be an object")
    ratings = {
        key: validate_rating(ratings_raw.get(key), key, case_id) for key in WEIGHTS
    }
    score = round(sum(ratings[key] * weight for key, weight in WEIGHTS.items()), 1)
    result = dict(item)
    result["case_id"] = case_id
    result["similarity_score"] = score
    result["similarity_band"] = band(score, ratings)
    result["gate_flags"] = [
        label
        for condition, label in (
            (ratings["legal_relation"] < 40, "legal-relation-mismatch"),
            (ratings["issue"] < 40, "issue-mismatch"),
            (ratings["decisive_facts"] < 40, "decisive-facts-weak"),
        )
        if condition
    ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="JSON file or - for stdin")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        raw = (
            sys.stdin.read()
            if args.input == "-"
            else Path(args.input).read_text(encoding="utf-8")
        )
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("cases")
        if not isinstance(items, list):
            raise ValueError("input must be a list or an object containing a cases list")
        scored = [score_case(item, i + 1) for i, item in enumerate(items)]
        scored.sort(key=lambda x: (-float(x["similarity_score"]), str(x["case_id"])))
        json.dump(
            {"weights": WEIGHTS, "cases": scored},
            sys.stdout,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
        sys.stdout.write("\n")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
