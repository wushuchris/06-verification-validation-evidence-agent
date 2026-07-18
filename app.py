from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd

from src.reporting import ReportFormatter
from src.schemas import EvidenceItem
from src.verifier import VerificationAgent


SAMPLE_CASES_PATH = Path(__file__).resolve().parent / "data" / "sample_cases.json"

agent = VerificationAgent()
formatter = ReportFormatter()


def _load_sample_cases() -> list[dict[str, Any]]:
    """Load sample cases from the JSON demo dataset."""
    data = json.loads(SAMPLE_CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Sample cases file must contain a JSON list.")
    return data


SAMPLE_CASES = _load_sample_cases()


def load_sample(title: str) -> tuple[str, str, str]:
    """Return the answer text, evidence JSON, and a sample description for a selected demo case."""
    for case in SAMPLE_CASES:
        if case.get("title") == title:
            answer_text = str(case.get("answer_text", ""))
            evidence_json = json.dumps(case.get("evidence", []), indent=2)
            description = (
                f"**Description:** {case.get('description', '')}\n\n"
                f"**Expected verdict:** {case.get('expected_verdict', '')}"
            )
            return answer_text, evidence_json, description

    raise gr.Error(f"Sample '{title}' could not be found.")


def parse_evidence(evidence_json: str) -> list[EvidenceItem]:
    """Parse evidence JSON into EvidenceItem objects."""
    if not evidence_json or not str(evidence_json).strip():
        raise ValueError("Evidence JSON must not be empty.")

    try:
        payload = json.loads(evidence_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise ValueError("Evidence JSON must be a non-empty list.")
    if not payload:
        raise ValueError("Evidence JSON must not be empty.")

    evidence: list[EvidenceItem] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Evidence item at index {index} must be an object.")

        missing = [field for field in ["evidence_id", "text", "source", "source_type", "reliability_score"] if field not in item]
        if missing:
            raise ValueError(f"Evidence item at index {index} is missing fields: {', '.join(missing)}")

        try:
            evidence.append(
                EvidenceItem(
                    evidence_id=str(item["evidence_id"]),
                    text=str(item["text"]),
                    source=str(item.get("source", "")),
                    source_type=str(item.get("source_type", "unknown")),
                    reliability_score=float(item["reliability_score"]),
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid evidence fields at index {index}: {exc}") from exc

    return evidence


def create_audit_package(report: Any) -> str:
    """Create a temporary audit package containing JSON, CSV, and Markdown outputs."""
    temp_dir = Path(tempfile.mkdtemp(prefix="verification_audit_", dir=None))
    report_dir = temp_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "verification_report.json"
    csv_path = report_dir / "verification_report.csv"
    markdown_path = report_dir / "verification_report.md"

    json_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    formatter.save_csv(report, csv_path)
    formatter.save_markdown(report, markdown_path)

    archive_path = temp_dir / "verification_audit.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(json_path, arcname=json_path.name)
        archive.write(csv_path, arcname=csv_path.name)
        archive.write(markdown_path, arcname=markdown_path.name)

    return str(archive_path)


def run_verification(answer_text: str, evidence_json: str) -> tuple[str, pd.DataFrame, str, dict[str, Any], str]:
    """Verify the supplied answer and return summary, claims, report, JSON, and an audit archive."""
    if not answer_text or not str(answer_text).strip():
        raise gr.Error("Please enter an AI-generated answer before verifying.")

    evidence = parse_evidence(evidence_json)
    report = agent.verify_text(str(answer_text).strip(), evidence)

    summary_markdown = formatter.summary_markdown(report)
    claims_dataframe = formatter.claims_dataframe(report)
    detailed_markdown = formatter.full_markdown(report)
    structured_json = report.model_dump(mode="json")
    audit_package = create_audit_package(report)

    return summary_markdown, claims_dataframe, detailed_markdown, structured_json, audit_package


def build_app() -> gr.Blocks:
    """Build the Gradio interface for the verification workflow."""
    with gr.Blocks(title="Verification, Validation & Evidence Agent") as demo:
        gr.Markdown(
            "The agent audits AI-generated factual claims against supplied evidence. "
            "Semantic and lexical matching retrieve relevant evidence. Deterministic rules assign statuses and overall verdicts. "
            "Human review is required for contradictions, unverifiable claims, missing citations, or citation mismatches. "
            "The tool does not independently prove that supplied source documents are truthful."
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Try a Demonstration")
                demo_dropdown = gr.Dropdown(
                    choices=[case["title"] for case in SAMPLE_CASES],
                    label="Sample Cases",
                    value=SAMPLE_CASES[0]["title"],
                )
                load_button = gr.Button("Load Demonstration")
                sample_output = gr.Markdown()

        with gr.Group():
            gr.Markdown("### Verify Claims")
            answer_input = gr.Textbox(label="AI-Generated Answer", lines=8)
            evidence_input = gr.Textbox(
                label="Evidence JSON",
                lines=12,
                value='[\n  {\n    "evidence_id": "E1",\n    "text": "The project launched on June 15.",\n    "source": "Launch report",\n    "source_type": "report",\n    "reliability_score": 0.95\n  }\n]',
            )
            gr.Markdown(
                "Example evidence format:\n```json\n[\n  {\n    \"evidence_id\": \"E1\",\n    \"text\": \"The project launched on June 15.\",\n    \"source\": \"Launch report\",\n    \"source_type\": \"report\",\n    \"reliability_score\": 0.95\n  }\n]\n```"
            )

            with gr.Row():
                verify_button = gr.Button("Verify Claims", variant="primary")
                clear_button = gr.Button("Clear")

        with gr.Tab("Summary"):
            summary_output = gr.Markdown()
        with gr.Tab("Claim Results"):
            claims_output = gr.Dataframe(label="Claim Results", interactive=False)
        with gr.Tab("Detailed Report"):
            detailed_output = gr.Markdown()
        with gr.Tab("Structured JSON"):
            json_output = gr.JSON()
        with gr.Tab("Download"):
            download_output = gr.File(label="Download Audit Package")

        def load_demo(selected_title: str) -> tuple[str, str, str]:
            return load_sample(selected_title)

        load_button.click(load_demo, inputs=demo_dropdown, outputs=[answer_input, evidence_input, sample_output])

        verify_button.click(
            run_verification,
            inputs=[answer_input, evidence_input],
            outputs=[summary_output, claims_output, detailed_output, json_output, download_output],
        )

        def clear_inputs() -> tuple[str, str, str, pd.DataFrame, str, dict[str, Any], str]:
            return "", "", "", pd.DataFrame(), "", {}, ""

        clear_button.click(
            clear_inputs,
            inputs=None,
            outputs=[answer_input, evidence_input, summary_output, claims_output, detailed_output, json_output, download_output],
        )

    return demo


demo = build_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    demo.launch(server_name="0.0.0.0", server_port=port)
