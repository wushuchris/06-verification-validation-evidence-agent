"""Business-first presentation helpers for Agent 6."""

from __future__ import annotations

from html import escape

from src.schemas import VerificationEvent, VerificationReport


APP_CSS = """
.gradio-container {
    max-width: 1080px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}
.agent-shell { max-width: 1080px; margin: 0 auto; }
.hero-card {
    border: 1px solid rgba(148,163,184,.28);
    border-radius: 22px;
    padding: 26px 28px;
    margin-bottom: 14px;
    background: linear-gradient(135deg, rgba(37,99,235,.13), rgba(16,185,129,.07));
}
.hero-card h1 { margin: 4px 0 9px; font-size: 2.18rem; line-height: 1.12; max-width: 900px; }
.hero-card p { margin: 0; max-width: 850px; font-size: 1.06rem; line-height: 1.58; opacity: .90; }
.eyebrow { text-transform: uppercase; letter-spacing: .11em; font-size: .76rem; font-weight: 780; opacity: .72; }
.info-card, .boundary-card, .verdict-card, .activity-panel, .decision-card, .claim-card {
    border: 1px solid rgba(148,163,184,.26);
    border-radius: 15px;
    padding: 16px 18px;
    margin: 9px 0;
    background: rgba(148,163,184,.035);
}
.boundary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.boundary-title { font-weight: 800; margin-bottom: 7px; }
.verdict-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 10px 0 18px; }
.verdict-card strong { display: block; font-size: 1.06rem; margin-bottom: 5px; }
.activity-header { display: flex; align-items: center; gap: 10px; margin-bottom: 11px; }
.status-badge { display: inline-block; border-radius: 999px; padding: 4px 10px; font-size: .78rem; font-weight: 800; letter-spacing: .04em; }
.status-idle { background: rgba(148,163,184,.15); }
.status-running { background: rgba(245,158,11,.16); }
.status-complete { background: rgba(34,197,94,.16); }
.spinner { width: 15px; height: 15px; border: 2px solid rgba(120,120,120,.28); border-top-color: currentColor; border-radius: 50%; animation: spin .85s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.event-feed { display: flex; flex-direction: column; gap: 8px; }
.event-feed-complete { max-height: 360px; overflow-y: auto; padding-right: 4px; }
.event-row { padding: 10px 12px; border-radius: 10px; background: var(--background-fill-primary); line-height: 1.45; }
.event-label { display: inline-block; min-width: 145px; font-weight: 780; }
.event-meta { opacity: .72; font-size: .86rem; margin-top: 4px; }
.decision-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 9px; }
.decision-word { font-size: 1.5rem; font-weight: 850; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; margin: 13px 0; }
.metric { text-align: center; padding: 11px; border-radius: 10px; background: var(--background-fill-primary); }
.metric strong { display: block; font-size: 1.30rem; }
.claim-list { display: grid; grid-template-columns: 1fr; gap: 9px; }
.claim-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.claim-title { font-weight: 800; }
.claim-status { border-radius: 999px; padding: 3px 9px; font-size: .77rem; font-weight: 800; white-space: nowrap; background: rgba(148,163,184,.14); }
.claim-text { margin: 9px 0; line-height: 1.48; }
.claim-meta { font-size: .89rem; opacity: .80; line-height: 1.48; }
@media (max-width: 760px) {
    .boundary-grid, .verdict-grid, .metric-grid { grid-template-columns: 1fr; }
    .hero-card h1 { font-size: 1.85rem; }
}
"""


HERO_HTML = """
<div class="hero-card">
  <div class="eyebrow">Agent 6 · Evidence verification boundary</div>
  <h1>Can this AI-generated answer clear an evidence review before someone relies on it?</h1>
  <p>
    This agent decomposes an AI answer into factual claims, matches each claim against supplied
    evidence, checks citations and contradictions, and assigns a deterministic PASS, REVIEW, or
    FAIL verdict. It evaluates <strong>alignment to the evidence you provide</strong>—it does not
    independently prove that the underlying sources are true.
  </p>
</div>
"""


BUSINESS_CASE_HTML = """
<div class="info-card">
  <strong>Why would a business care?</strong><br>
  AI-generated summaries can sound polished even when a number is wrong, a citation points to the
  wrong source, or the available evidence is too weak to justify confidence. Agent 6 acts as a
  review gate between generated content and downstream reliance: <strong>retrieve relevant evidence,
  apply deterministic checks, and escalate uncertainty to a human.</strong>
</div>
"""


EVIDENCE_BOUNDARY_HTML = """
<div class="boundary-card boundary-grid">
  <div>
    <div class="boundary-title">✅ This system can conclude</div>
    <ul>
      <li>whether extracted claims align with the supplied evidence;</li>
      <li>whether numerical or negation conflicts are detected;</li>
      <li>whether citations are missing or appear mismatched;</li>
      <li>whether evidence reliability or ambiguity requires human review.</li>
    </ul>
  </div>
  <div>
    <div class="boundary-title">⛔ This system does not conclude</div>
    <ul>
      <li>that the supplied evidence is independently true;</li>
      <li>that a PASS establishes real-world truth;</li>
      <li>that the evidence collection is complete;</li>
      <li>that expert judgment can be removed from high-stakes review.</li>
    </ul>
  </div>
</div>
"""


VERDICT_GUIDE_HTML = """
<div class="verdict-grid">
  <div class="verdict-card"><strong>PASS</strong>Every extracted claim is supported under the supplied evidence and current deterministic rules.</div>
  <div class="verdict-card"><strong>REVIEW</strong>No hard failure is required, but partial support, unverifiable content, citation issues, or other uncertainty needs human judgment.</div>
  <div class="verdict-card"><strong>FAIL</strong>At least one extracted claim is unsupported or contradicted by the supplied evidence.</div>
</div>
"""


ARCHITECTURE_MARKDOWN = """
### Verification architecture

```text
AI-generated answer
      ↓
Deterministic claim extraction
      ↓
Semantic + lexical evidence matching
      ↓
Application-owned verification rules
  ├─ contradiction checks
  ├─ citation checks
  ├─ reliability checks
  └─ evidence-strength thresholds
      ↓
Claim-level statuses
      ↓
PASS / REVIEW / FAIL aggregation
      ↓
Human-review gate + audit exports
```

The reusable primitive is an **evidence-validation boundary**: retrieval proposes the most relevant
support, deterministic application rules assign the verification status, and ambiguous cases are
escalated rather than silently promoted to fact.
"""


LIMITS_MARKDOWN = """
### What the verdict means

A PASS means the extracted claims are supported by the **supplied evidence collection** under the
current deterministic rules. It is deliberately narrower than a claim of truth.

The verifier does not browse for independent sources, certify source authenticity, or guarantee that
the evidence set is complete. Semantic similarity helps retrieve candidate evidence; it does not by
itself decide truth. Deterministic contradiction, citation, reliability, and threshold rules own the
claim status.

This makes Agent 6 useful as a quality-control and escalation layer, not as a replacement for expert
judgment in consequential decisions.
"""


EVENT_LABELS = {
    "verification_started": "Review started",
    "claims_extracted": "Claims extracted",
    "evidence_matching_started": "Evidence matching",
    "evidence_matched": "Evidence matched",
    "claim_verified": "Claim classified",
    "report_completed": "Verdict ready",
}


def idle_activity_html() -> str:
    return """
    <div class="activity-panel">
      <div class="activity-header">
        <span class="status-badge status-idle">READY</span>
        <strong>Live Evidence Review</strong>
      </div>
      <div class="event-row">Load a synthetic case or provide an answer and evidence, then run verification.</div>
    </div>
    """


def starting_activity_html() -> str:
    return """
    <div class="activity-panel">
      <div class="activity-header">
        <span class="status-badge status-running">RUNNING</span>
        <span class="spinner"></span>
        <strong>Live Evidence Review</strong>
      </div>
      <div class="event-row">Preparing the supplied answer and evidence for verification.</div>
    </div>
    """


def render_activity(events: list[VerificationEvent], complete: bool = False) -> str:
    if complete:
        badge = '<span class="status-badge status-complete">COMPLETE</span>'
        spinner = ""
        feed_class = "event-feed event-feed-complete"
        visible = events
    else:
        badge = '<span class="status-badge status-running">RUNNING</span>'
        spinner = '<span class="spinner"></span>'
        feed_class = "event-feed"
        visible = events[-9:]

    rows: list[str] = []
    for event in visible:
        meta: list[str] = []
        if event.claim is not None:
            meta.append(f"claim: {escape(event.claim.claim_id)}")
        if event.matches:
            meta.append(f"matches: {len(event.matches)}")
        if event.claim_result is not None:
            meta.append(f"status: {escape(event.claim_result.status.value)}")
        if event.report is not None:
            meta.append(f"verdict: {escape(event.report.verdict.value)}")

        meta_html = ""
        if meta:
            meta_html = f'<div class="event-meta">{" · ".join(meta)}</div>'

        rows.append(
            '<div class="event-row">'
            f'<span class="event-label">{escape(EVENT_LABELS[event.event])}</span>'
            f'{escape(event.message)}{meta_html}</div>'
        )

    if not rows:
        rows.append('<div class="event-row">Waiting for verification to begin.</div>')

    return (
        '<div class="activity-panel">'
        f'<div class="activity-header">{badge}{spinner}<strong>Live Evidence Review</strong></div>'
        f'<div class="{feed_class}">{"".join(rows)}</div>'
        '</div>'
    )


def render_decision(report: VerificationReport | None) -> str:
    if report is None:
        return '<div class="decision-card">Run verification to see the evidence-review decision.</div>'

    verdict = report.verdict.value
    if verdict == "pass":
        headline = "Evidence-aligned within the supplied record"
        guidance = (
            "All extracted claims are supported under the current rules. This does not independently "
            "prove that the supplied sources are true or complete."
        )
    elif verdict == "review":
        headline = "Hold for human review"
        guidance = (
            "The answer did not trigger a hard FAIL, but at least one claim, citation, or evidence-quality "
            "issue needs human judgment before reliance."
        )
    else:
        headline = "Do not rely on the answer as written"
        guidance = (
            "At least one extracted claim is unsupported or contradicted by the supplied evidence. "
            "The answer should be corrected or the evidence record changed before reuse."
        )

    scrutiny = report.partially_supported_claims + report.not_verifiable_claims
    failed = report.unsupported_claims + report.contradicted_claims

    return f"""
    <div class="decision-card">
      <div class="decision-head">
        <span class="status-badge status-complete">{escape(verdict.upper())}</span>
        <span class="decision-word">{escape(headline)}</span>
      </div>
      <p>{escape(guidance)}</p>
      <div class="metric-grid">
        <div class="metric"><strong>{report.total_claims}</strong>claims</div>
        <div class="metric"><strong>{report.supported_claims}</strong>supported</div>
        <div class="metric"><strong>{scrutiny}</strong>needs scrutiny</div>
        <div class="metric"><strong>{failed}</strong>failed checks</div>
      </div>
      <p style="margin-bottom:0;"><strong>Human review required:</strong> {'Yes' if report.human_review_required else 'No'} · <strong>Overall confidence:</strong> {report.overall_confidence * 100:.1f}%</p>
    </div>
    """


def render_claim_cards(report: VerificationReport | None) -> str:
    if report is None:
        return '<div class="claim-card">Claim-level evidence findings will appear here after verification.</div>'

    cards: list[str] = []
    for item in report.claim_results:
        cited = ", ".join(item.claim.cited_evidence_ids) if item.claim.cited_evidence_ids else "None"
        matched = ", ".join(match.evidence_id for match in item.matched_evidence) if item.matched_evidence else "None"
        issues = "; ".join(item.issues) if item.issues else "None"
        cards.append(
            '<div class="claim-card">'
            '<div class="claim-head">'
            f'<div class="claim-title">{escape(item.claim.claim_id)}</div>'
            f'<span class="claim-status">{escape(item.status.value.replace("_", " ").upper())}</span>'
            '</div>'
            f'<div class="claim-text">{escape(item.claim.text)}</div>'
            f'<div class="claim-meta"><strong>Evidence strength:</strong> {escape(item.evidence_strength.value)} · '
            f'<strong>Confidence:</strong> {item.confidence * 100:.1f}% · '
            f'<strong>Human review:</strong> {"Yes" if item.human_review_required else "No"}<br>'
            f'<strong>Cited:</strong> {escape(cited)} · <strong>Matched:</strong> {escape(matched)}<br>'
            f'<strong>Issues:</strong> {escape(issues)}<br>'
            f'<strong>Why:</strong> {escape(item.rationale)}</div>'
            '</div>'
        )

    return f'<div class="claim-list">{"".join(cards)}</div>'
