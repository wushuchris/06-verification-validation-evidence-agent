from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd

from src.demo_presentation import (
    APP_CSS,
    ARCHITECTURE_MARKDOWN,
    BUSINESS_CASE_HTML,
    EVIDENCE_BOUNDARY_HTML,
    HERO_HTML,
    LIMITS_MARKDOWN,
    VERDICT_GUIDE_HTML,
    idle_activity_html,
    render_activity,
    render_claim_cards,
    render_decision,
    starting_activity_html,
)
from src.reporting import ReportFormatter
from src.schemas import EvidenceItem, VerificationEvent, VerificationReport, VerificationRequest
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
DEFAULT_SAMPLE_TITLE = "Contradicted Revenue Claim"


def load_sample(title: str) -> tuple[str, str, str]:
    """Return the answer text, evidence JSON, and a sample description for a selected demo case."""
    for case in SAMPLE_CASES:
        if case.get("title") == title:
            answer_text = str(case.get("answer_text", ""))
            evidence_json = json.dumps(case.get("evidence", []), indent=2)
            description = (
                f"**Scenario:** {case.get('description', '')}\n\n"
                f"**Expected evidence-review verdict:** {str(case.get('expected_verdict', '')).upper()}"
            )
            return answer_text, evidence_json, description

    raise gr.Error(f"Sample '{title}' could not be found.")


DEFAULT_ANSWER, DEFAULT_EVIDENCE, DEFAULT_DESCRIPTION = load_sample(DEFAULT_SAMPLE_TITLE)


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

        missing = [
            field
            for field in ["evidence_id", "text", "source", "source_type", "reliability_score"]
            if field not in item
        ]
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


def create_audit_package(report: VerificationReport) -> str:
    """Create a temporary audit package containing JSON, CSV, and Markdown outputs."""
    temp_dir = Path(tempfile.mkdtemp(prefix="verification_audit_", dir=None))
    report_dir = temp_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "verification_report.json"
    csv_path = report_dir / "verification_report.csv"
    markdown_path = report_dir / "verification_report.md"

    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    formatter.save_csv(report, csv_path)
    formatter.save_markdown(report, markdown_path)

    archive_path = temp_dir / "verification_audit.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(json_path, arcname=json_path.name)
        archive.write(csv_path, arcname=csv_path.name)
        archive.write(markdown_path, arcname=markdown_path.name)

    return str(archive_path)


def run_verification(answer_text: str, evidence_json: str) -> tuple[str, pd.DataFrame, str, dict[str, Any], str]:
    """Preserve the original non-streaming verification callback contract."""
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


def _stream_outputs(events: list[VerificationEvent], report: VerificationReport | None = None):
    complete = report is not None
    if report is None:
        return (
            render_activity(events, complete=False),
            render_decision(None),
            render_claim_cards(None),
            pd.DataFrame(),
            "*Detailed audit content will appear after verification completes.*",
            {},
            None,
        )

    return (
        render_activity(events, complete=True),
        render_decision(report),
        render_claim_cards(report),
        formatter.claims_dataframe(report),
        formatter.full_markdown(report),
        report.model_dump(mode="json"),
        create_audit_package(report),
    )


def stream_verification(answer_text: str, evidence_json: str):
    """Stream real verification-stage events into the business-facing demo."""
    if not answer_text or not str(answer_text).strip():
        yield (
            idle_activity_html(),
            '<div class="decision-card">Please enter an AI-generated answer before verifying.</div>',
            render_claim_cards(None),
            pd.DataFrame(),
            "",
            {},
            None,
        )
        return

    yield (
        starting_activity_html(),
        render_decision(None),
        render_claim_cards(None),
        pd.DataFrame(),
        "*Verification is running.*",
        {},
        None,
    )

    events: list[VerificationEvent] = []

    try:
        evidence = parse_evidence(evidence_json)
        request = VerificationRequest(answer_text=str(answer_text).strip(), evidence=evidence)

        for event in agent.verify_iter(request):
            events.append(event)
            yield _stream_outputs(events, report=event.report)

    except Exception as exc:
        safe_message = str(exc) if isinstance(exc, ValueError) else "Verification could not complete."
        yield (
            render_activity(events, complete=True),
            f'<div class="decision-card"><strong>Verification stopped.</strong><br>{safe_message}</div>',
            render_claim_cards(None),
            pd.DataFrame(),
            "Verification stopped before a final report was produced.",
            {},
            None,
        )


def build_app() -> gr.Blocks:
    """Build the business-first Gradio interface for the verification workflow."""
    with gr.Blocks(title="Verification, Validation & Evidence Agent") as demo:
        with gr.Column(elem_classes=["agent-shell"]):
            gr.HTML(HERO_HTML)
            gr.HTML(BUSINESS_CASE_HTML)

            gr.Markdown("## The evidence boundary")
            gr.HTML(EVIDENCE_BOUNDARY_HTML)

            gr.Markdown("## What the three verdicts mean")
            gr.HTML(VERDICT_GUIDE_HTML)

            gr.Markdown("## Review an AI-generated answer")
            with gr.Row():
                demo_dropdown = gr.Dropdown(
                    choices=[case["title"] for case in SAMPLE_CASES],
                    label="Synthetic demonstration",
                    value=DEFAULT_SAMPLE_TITLE,
                    scale=3,
                )
                load_button = gr.Button("Load selected case", scale=1)

            sample_output = gr.Markdown(DEFAULT_DESCRIPTION)
            answer_input = gr.Textbox(
                label="AI-generated answer under review",
                lines=5,
                value=DEFAULT_ANSWER,
            )

            with gr.Accordion("Supplied evidence record", open=False):
                evidence_input = gr.Textbox(
                    label="Evidence JSON",
                    lines=12,
                    value=DEFAULT_EVIDENCE,
                )
                gr.Markdown(
                    "The verifier uses only this supplied evidence collection. Reliability scores are "
                    "inputs to the demo and are not independently established by the agent."
                )

            with gr.Row():
                verify_button = gr.Button("Run evidence review", variant="primary")
                clear_button = gr.Button("Clear")

            activity_output = gr.HTML(idle_activity_html())

            with gr.Tabs():
                with gr.Tab("Decision Review"):
                    decision_output = gr.HTML(render_decision(None))
                    claim_cards_output = gr.HTML(render_claim_cards(None))

                with gr.Tab("Claim Audit"):
                    claims_output = gr.Dataframe(label="Claim-level verification results", interactive=False)

                with gr.Tab("Evidence & Limits"):
                    gr.Markdown(LIMITS_MARKDOWN)

                with gr.Tab("Engineering Audit"):
                    detailed_output = gr.Markdown()
                    json_output = gr.JSON(label="Structured verification report")

                with gr.Tab("Architecture"):
                    gr.Markdown(ARCHITECTURE_MARKDOWN)

                with gr.Tab("Download"):
                    download_output = gr.File(label="Download JSON / CSV / Markdown audit package")

            load_button.click(
                load_sample,
                inputs=demo_dropdown,
                outputs=[answer_input, evidence_input, sample_output],
                show_progress="hidden",
            )

            verify_button.click(
                stream_verification,
                inputs=[answer_input, evidence_input],
                outputs=[
                    activity_output,
                    decision_output,
                    claim_cards_output,
                    claims_output,
                    detailed_output,
                    json_output,
                    download_output,
                ],
                show_progress="hidden",
            )

            def clear_inputs():
                return (
                    "",
                    "",
                    "",
                    idle_activity_html(),
                    render_decision(None),
                    render_claim_cards(None),
                    pd.DataFrame(),
                    "",
                    {},
                    None,
                )

            clear_button.click(
                clear_inputs,
                inputs=None,
                outputs=[
                    answer_input,
                    evidence_input,
                    sample_output,
                    activity_output,
                    decision_output,
                    claim_cards_output,
                    claims_output,
                    detailed_output,
                    json_output,
                    download_output,
                ],
                show_progress="hidden",
            )

    return demo


demo = build_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    demo.launch(server_name="0.0.0.0", server_port=port, css=APP_CSS)
