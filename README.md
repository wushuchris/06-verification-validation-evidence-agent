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
short_description: Audit AI-generated claims against supplied evidence.
models:
  - sentence-transformers/all-MiniLM-L6-v2
---

# Verification, Validation & Evidence Agent

A deterministic evidence-auditing agent that extracts factual claims from AI-generated text, matches those claims against supplied evidence, validates citations, detects contradictions, and produces an auditable PASS, REVIEW, or FAIL verdict.

## Overview

This project evaluates whether AI-generated factual claims are supported by a user-supplied evidence collection. It does not independently prove that the supplied sources are true. Instead, it evaluates alignment between claims and supplied evidence.

> Semantic matching retrieves. Deterministic rules decide. Humans resolve uncertainty.

## What It Checks

The agent checks:

- factual claim coverage
- semantic evidence relevance
- lexical overlap
- explicit numerical contradictions
- negation contradictions
- missing evidence citations
- citation mismatches
- evidence reliability
- human-review requirements

## Claim Statuses

The verification engine assigns one of these claim-level statuses:

- supported: the claim is well aligned with the supplied evidence.
- partially_supported: the match is present but weaker, less reliable, or only partly aligned.
- unsupported: the claim is not meaningfully supported by the evidence.
- contradicted: the evidence directly conflicts with the claim.
- not_verifiable: the supplied evidence is insufficient or too unrelated to validate the claim.

## Overall Verdicts

The workflow aggregates claim results into one of three verdicts:

- PASS: every extracted claim is supported and no human review is required.
- REVIEW: no claim fails, but at least one claim is partially supported, unverifiable, or requires human review.
- FAIL: at least one claim is unsupported or contradicted.

## Architecture

```text
AI-Generated Answer
        |
        v
Claim Extractor
        |
        v
Evidence Matcher
  - semantic similarity
  - lexical overlap
        |
        v
Deterministic Rules Engine
  - contradiction checks
  - citation validation
  - reliability checks
        |
        v
Verification Report
  - claim-level results
  - PASS / REVIEW / FAIL
  - JSON / CSV / Markdown audit package
```

The main modules are:

- src/schemas.py: shared Pydantic models for claims, evidence, matches, and reports.
- src/claim_extractor.py: deterministic extraction of factual claims from answer text.
- src/evidence_matcher.py: evidence matching using semantic similarity and lexical overlap.
- src/rules.py: deterministic verification heuristics for contradictions, reliability, and citation issues.
- src/verifier.py: orchestration layer that assembles claim extraction, matching, and verification.
- src/reporting.py: formatting and export helpers for Markdown, CSV, and JSON outputs.
- app.py: local Gradio interface for interactive verification and audit-package download.
- evals/run_evaluation.py: deterministic evaluation runner for the synthetic benchmark cases.

## Technology

This project uses:

- Python 3.11+
- Pydantic
- Sentence Transformers
- scikit-learn
- pandas
- Gradio
- pytest

The application uses the local public model:

- sentence-transformers/all-MiniLM-L6-v2

No hosted AI API or API key is required.

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
  schemas.py
  claim_extractor.py
  evidence_matcher.py
  rules.py
  verifier.py
  reporting.py
tests/
  test_rules.py
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

On Windows, activate the virtual environment with:

```powershell
.venv\Scripts\activate
```

## Run the Application

```bash
python app.py
```

The local interface opens on port 7860.

## Evidence Input Format

Provide evidence as a JSON array of objects such as:

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

- [E1]
- [E1, E2]
- [E1][E2]

## Demonstration Cases

The repository includes synthetic, public-safe demonstration cases such as:

- a fully supported launch report
- a preliminary finding supported by low-reliability evidence
- a contradicted revenue claim

These examples are fictional and intended for demonstration only.

## Testing

Run the automated suite with:

```bash
pytest -q
```

The current suite contains 16 automated tests covering:

- supported claims
- numerical contradictions
- negation contradictions
- missing citations
- citation mismatches
- irrelevant evidence
- PASS, REVIEW, and FAIL orchestration
- human-review escalation

## Evaluation

Run the synthetic evaluation set with:

```bash
python -m evals.run_evaluation
```

The current evaluation suite contains six targeted cases. The most recent run reported:

- 6 of 6 cases passed
- case accuracy: 100%
- verdict accuracy: 100%
- claim-status accuracy: 100%
- human-review accuracy: 100%

These results apply only to the small included synthetic evaluation set and are not evidence of general real-world accuracy. Detailed outputs are stored in:

- outputs/evaluation_results.csv
- outputs/evaluation_summary.json

## Audit Outputs

Each verification can export:

- Markdown report
- JSON report
- CSV claim table
- ZIP audit package

## Limitations

This tool is intentionally heuristic and should be used carefully:

- similarity does not prove truth
- the agent depends on the supplied evidence
- deterministic contradiction detection is conservative and heuristic
- nuanced paraphrases may be misclassified
- source reliability is supplied by the user rather than independently established
- complex multi-hop reasoning may require manual review
- this tool should support, not replace, expert judgment in high-stakes decisions

## Privacy and Security

- no API keys are required
- no hosted LLM service is called
- user-generated audit packages are written to temporary runtime storage
- private documents should not be committed to the public repository

## License

This project is released under the MIT License.
