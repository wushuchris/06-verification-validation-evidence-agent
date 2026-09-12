---
title: Verification Validation Evidence Agent
emoji: ✅
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.20.0
python_version: 3.11
app_file: app.py
pinned: false
short_description: Gate AI-generated claims against supplied evidence.
models:
  - sentence-transformers/all-MiniLM-L6-v2
---

# Verification, Validation & Evidence Agent

A deterministic **AI evidence-review gate** that extracts factual claims from AI-generated text, matches those claims against supplied evidence, validates citations, detects contradictions, and produces an auditable **PASS, REVIEW, or FAIL** verdict before someone relies on the answer.

**Live Demo:** [Hugging Face Space](https://huggingface.co/spaces/FlyingNunchucks/06-verification-validation-evidence-agent)

> **Semantic matching retrieves. Deterministic rules decide. Humans resolve uncertainty.**

## Business Problem

AI-generated answers can sound confident even when individual statements are weakly supported, contradicted by available evidence, cited incorrectly, or not verifiable from the material provided.

Agent 6 inserts an evidence-review boundary between an AI answer and downstream reliance:

```text
AI-generated answer
        |
        v
Extract factual claims
        |
        v
Match claims to supplied evidence
        |
        v
Check contradictions, citations, and reliability
        |
        v
Classify each claim
        |
        v
PASS / REVIEW / FAIL
        |
        v
Human review when uncertainty remains
```

The system is intentionally conservative. It does **not** independently prove that the supplied evidence is true.

## The Evidence Boundary

The verifier can answer questions such as:

- Does this claim align with the supplied evidence?
- Is the strongest matching evidence sufficiently relevant?
- Does the claim conflict with an explicit number or negation in the evidence?
- Does the cited evidence actually support the claim?
- Is the supplied evidence too weak or unrelated to verify the claim?
- Should a human review the result before relying on it?

It cannot establish that the source documents themselves are truthful, complete, current, unbiased, or authoritative beyond the information supplied to the system.

**A PASS therefore means:** the extracted claims align with the supplied evidence under the implemented verification rules and no human-review condition was triggered.

**A PASS does not mean:** independently proven real-world truth.

## Claim Statuses

Each extracted claim receives one deterministic status:

- **supported** — the claim is well aligned with the supplied evidence.
- **partially_supported** — relevant support exists, but the match or evidence quality is weaker.
- **unsupported** — the available evidence does not sufficiently support the claim.
- **contradicted** — supplied evidence directly conflicts with the claim under the implemented contradiction checks.
- **not_verifiable** — the supplied evidence is insufficient or too unrelated to validate the claim.

## Overall Verdicts

Claim-level results roll up into one of three workflow outcomes:

- **PASS** — every extracted claim is supported and no human review is required.
- **REVIEW** — no claim fails, but at least one claim is partially supported, not verifiable, citation-problematic, or otherwise requires human review.
- **FAIL** — at least one claim is unsupported or contradicted.

This separates automated evidence review from final human judgment.

## Live Verification Observability

The verification engine exposes a reusable `verify_iter()` interface that yields events from the **real deterministic verification workflow**.

The live demo can therefore show actual stages as they occur:

1. `verification_started`
2. `claims_extracted`
3. `evidence_matching_started`
4. `evidence_matched`
5. `claim_verified`
6. `report_completed`

The standard `verify()` and `verify_text()` APIs still consume this same workflow and return the final report, so the interactive demo is not a separate simulated verification path.

## Business-First Demo

The Hugging Face Space was redesigned around the question:

> **Can this AI-generated answer clear an evidence review before someone relies on it?**

The presentation uses a centered **1080px** reading path and leads with the decision story rather than raw JSON.

The default synthetic demonstration is a **contradicted revenue claim**, making the failure case immediately visible. The demo includes:

- a clear explanation of the evidence boundary,
- a plain-English PASS / REVIEW / FAIL guide,
- editable synthetic AI output,
- supplied evidence in a secondary accordion,
- **Live Evidence Review** driven by real `verify_iter()` events,
- a business-facing Decision Review,
- readable claim-level cards,
- a Claim Audit table,
- explicit Evidence & Limits guidance,
- a full Engineering Audit,
- architecture documentation,
- and downloadable JSON / CSV / Markdown audit artifacts.

The generic Gradio progress treatment is hidden so the verification workflow itself owns the visible execution experience.

## Architecture

```text
AI-Generated Answer
        |
        v
Claim Extractor
  - deterministic sentence/claim parsing
  - citation extraction
        |
        v
Evidence Matcher
  - sentence-transformer semantic similarity
  - lexical overlap
  - cited-evidence retention
        |
        v
Deterministic Rules Engine
  - relevance thresholds
  - explicit numeric contradiction checks
  - negation contradiction checks
  - citation validation
  - reliability checks
  - human-review escalation
        |
        v
Verification Report
  - claim-level status
  - evidence strength
  - confidence
  - issues / rationale
  - PASS / REVIEW / FAIL
        |
        v
Audit Package
  - JSON
  - CSV
  - Markdown
```

### Main Modules

- `src/schemas.py` — Pydantic models for claims, evidence, matches, verification events, and reports.
- `src/claim_extractor.py` — deterministic extraction of factual claims and citation IDs.
- `src/evidence_matcher.py` — semantic and lexical evidence matching.
- `src/rules.py` — deterministic contradiction, relevance, reliability, and citation rules.
- `src/verifier.py` — orchestration, `verify_iter()` observability, and final verdict aggregation.
- `src/reporting.py` — Markdown, CSV, JSON, and audit-package formatting.
- `src/demo_presentation.py` — business-facing presentation and live verification rendering.
- `app.py` — Gradio application and streaming demo callback.
- `evals/run_evaluation.py` — deterministic synthetic benchmark runner and deployment gate.

## Technology

- Python 3.11+
- Pydantic
- Sentence Transformers
- `sentence-transformers/all-MiniLM-L6-v2`
- scikit-learn
- pandas
- Gradio
- pytest
- GitHub Actions
- Hugging Face Spaces

The semantic matcher uses a local public sentence-transformer model. No hosted LLM API or API key is required for runtime verification.

## Repository Structure

```text
app.py
data/
  sample_cases.json
evals/
  evaluation_cases.json
  run_evaluation.py
outputs/
src/
  claim_extractor.py
  demo_presentation.py
  evidence_matcher.py
  reporting.py
  rules.py
  schemas.py
  verifier.py
tests/
  test_presentation.py
  test_rules.py
  test_verification_events.py
  test_verifier.py
requirements.txt
```

## Installation

```bash
git clone https://github.com/wushuchris/06-verification-validation-evidence-agent.git
cd 06-verification-validation-evidence-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```powershell
.venv\Scripts\activate
```

## Run the Application

```bash
python app.py
```

The local interface opens on port 7860.

## Evidence Input Format

Evidence is supplied as a JSON array:

```json
[
  {
    "evidence_id": "E1",
    "text": "The project launched on June 15.",
    "source": "Launch report",
    "source_type": "report",
    "reliability_score": 0.95
  }
]
```

Claims can cite evidence using forms such as:

- `[E1]`
- `[E1, E2]`
- `[E1][E2]`

The `reliability_score` is supplied as an input. The agent does not independently establish source reliability.

## Demonstration Cases

The repository contains synthetic, public-safe examples including:

- a fully supported launch report,
- a preliminary finding backed by low-reliability evidence,
- and a contradicted revenue claim.

All demo data is fictional.

## Testing

Run the automated suite with:

```bash
python -m pytest -q
```

The current suite contains **20 automated tests** covering the verification rules and orchestration plus the retrofit's observability and presentation contracts, including:

- supported claims,
- numerical contradictions,
- negation contradictions,
- missing citations,
- citation mismatches,
- irrelevant evidence,
- PASS / REVIEW / FAIL aggregation,
- human-review escalation,
- real incremental `verify_iter()` events,
- preservation of the normal `verify()` API,
- centered business-first presentation,
- evidence-boundary language,
- and streamed intermediate verification frames before the final verdict.

The production-validated suite passed **20 tests in 2.93 seconds** on the final retrofit gate before human approval.

## Evaluation

Run the synthetic benchmark with:

```bash
python -m evals.run_evaluation
```

The evaluation suite contains six targeted cases:

1. two fully supported claims,
2. numeric contradiction,
3. negation contradiction,
4. low-reliability supporting evidence,
5. citation mismatch,
6. insufficient relevant evidence.

The production gate reported:

- **6 of 6 cases passed**
- case accuracy: **100%**
- verdict accuracy: **100%**
- claim-status accuracy: **100%**
- human-review accuracy: **100%**

These results apply only to the included synthetic benchmark. They are not evidence of general real-world verification accuracy.

The evaluation runner now exits nonzero when any benchmark case fails, allowing the benchmark to function as a real deployment gate rather than an informational report only.

## Test-Gated Deployment

Production deployment follows:

```text
Push to main
    |
    v
Install dependencies
    |
    v
20 automated tests
    |
    v
6-case verification evaluation
    |
    v
Only if both are green
    |
    v
GitHub -> Hugging Face Space
```

The deployment workflow prefers the repository deployment secret `HF_DEPLOY_TOKEN` while retaining compatibility with the older `HF_TOKEN` configuration.

The final upgraded build passed both the automated suite and evaluation gate before the Hugging Face synchronization completed successfully.

## Audit Outputs

Each completed verification can export:

- Markdown report,
- JSON report,
- CSV claim table,
- and a ZIP audit package containing all three.

## Limitations

This tool is intentionally bounded and heuristic:

- semantic similarity does not prove truth,
- the verifier depends on the supplied evidence collection,
- deterministic contradiction detection is conservative,
- nuanced paraphrases may be misclassified,
- evidence reliability scores are supplied rather than independently established,
- complex multi-hop reasoning may require expert review,
- missing evidence can produce uncertainty rather than a definitive conclusion,
- and high-stakes use should preserve qualified human judgment.

The system is designed to **surface uncertainty**, not hide it.

## Privacy and Security

- no hosted LLM API is required,
- no runtime API key is required for verification,
- audit packages are written to temporary runtime storage,
- public examples use synthetic data,
- and private documents or sensitive evidence should never be committed to this public repository.

## Engineering Pattern

Agent 6 established a reusable portfolio primitive:

> **Sources provide the evidence. Deterministic rules classify support. Humans resolve uncertainty.**

That primitive becomes a verification boundary reused by later workflow and multi-agent systems.

## License

This project is released under the MIT License.
