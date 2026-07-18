from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas import EvidenceItem
from src.verifier import VerificationAgent


def load_cases(path: str | Path) -> list[dict[str, object]]:
    """Load evaluation cases from a JSON file."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}, got {type(data).__name__}.")
    return data


def evaluate_cases(
    cases: list[dict[str, object]],
    agent: VerificationAgent | None = None,
) -> tuple[pandas.DataFrame, dict[str, object]]:
    """Evaluate the provided cases and return detailed results plus a summary."""
    agent = agent if agent is not None else VerificationAgent()

    rows: list[dict[str, object]] = []
    for case in cases:
        case_id = str(case.get("case_id", ""))
        title = str(case.get("title", ""))
        evaluation_focus = str(case.get("evaluation_focus", ""))
        expected_verdict = str(case.get("expected_verdict", ""))
        expected_claim_statuses = case.get("expected_claim_statuses", [])
        expected_human_review = bool(case.get("expected_human_review", False))

        try:
            evidence_payload = case.get("evidence", [])
            evidence = [
                EvidenceItem(
                    evidence_id=str(item["evidence_id"]),
                    text=str(item["text"]),
                    source=str(item.get("source", "")),
                    source_type=str(item.get("source_type", "unknown")),
                    reliability_score=float(item.get("reliability_score", 0.0)),
                )
                for item in evidence_payload
            ]
            report = agent.verify_text(str(case.get("answer_text", "")), evidence)
            actual_verdict = report.verdict.value
            actual_claim_statuses = [result.status.value for result in report.claim_results]
            actual_human_review = report.human_review_required

            verdict_correct = actual_verdict == expected_verdict
            statuses_correct = actual_claim_statuses == list(expected_claim_statuses)
            human_review_correct = actual_human_review == expected_human_review
            case_passed = verdict_correct and statuses_correct and human_review_correct
            error = ""
        except Exception as exc:  # noqa: BLE001
            actual_verdict = ""
            actual_claim_statuses = []
            actual_human_review = False
            verdict_correct = False
            statuses_correct = False
            human_review_correct = False
            case_passed = False
            error = str(exc)

        rows.append(
            {
                "case_id": case_id,
                "title": title,
                "evaluation_focus": evaluation_focus,
                "expected_verdict": expected_verdict,
                "actual_verdict": actual_verdict,
                "verdict_correct": verdict_correct,
                "expected_claim_statuses": ", ".join(str(item) for item in expected_claim_statuses),
                "actual_claim_statuses": ", ".join(actual_claim_statuses),
                "statuses_correct": statuses_correct,
                "expected_human_review": expected_human_review,
                "actual_human_review": actual_human_review,
                "human_review_correct": human_review_correct,
                "case_passed": case_passed,
                "error": error,
            }
        )

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "case_id",
            "title",
            "evaluation_focus",
            "expected_verdict",
            "actual_verdict",
            "verdict_correct",
            "expected_claim_statuses",
            "actual_claim_statuses",
            "statuses_correct",
            "expected_human_review",
            "actual_human_review",
            "human_review_correct",
            "case_passed",
            "error",
        ],
    )

    total_cases = len(dataframe)
    passed_cases = int(dataframe["case_passed"].sum()) if total_cases else 0
    failed_cases = total_cases - passed_cases
    case_accuracy = round(passed_cases / total_cases, 4) if total_cases else 0.0
    verdict_accuracy = round(int(dataframe["verdict_correct"].sum()) / total_cases, 4) if total_cases else 0.0
    status_accuracy = round(int(dataframe["statuses_correct"].sum()) / total_cases, 4) if total_cases else 0.0
    human_review_accuracy = round(int(dataframe["human_review_correct"].sum()) / total_cases, 4) if total_cases else 0.0

    summary = {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "case_accuracy": case_accuracy,
        "verdict_accuracy": verdict_accuracy,
        "status_accuracy": status_accuracy,
        "human_review_accuracy": human_review_accuracy,
    }
    return dataframe, summary


def save_results(
    dataframe: pandas.DataFrame,
    summary: dict[str, object],
    output_directory: str | Path = "outputs",
) -> tuple[Path, Path]:
    """Save the evaluation results as CSV and JSON summaries."""
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "evaluation_results.csv"
    summary_path = output_dir / "evaluation_summary.json"

    dataframe.to_csv(results_path, index=False, encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return results_path, summary_path


def main() -> None:
    """Run the evaluation workflow end to end."""
    cases = load_cases(Path("evals") / "evaluation_cases.json")
    dataframe, summary = evaluate_cases(cases)
    results_path, summary_path = save_results(dataframe, summary)

    print(dataframe.to_string(index=False))
    print(json.dumps(summary, indent=2))
    print(results_path)
    print(summary_path)


if __name__ == "__main__":
    main()
