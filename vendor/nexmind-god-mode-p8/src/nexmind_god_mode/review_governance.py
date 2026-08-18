from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


def release_decision_law(stage: str) -> List[str]:
    stage = str(stage or "CREATIVE_STAGE").upper()
    return [
        f"You are the commercial release gate for {stage}, not a perfection optimizer.",
        "Maintain the full creative-quality standard. Do not accept generic, contradictory, off-brief, implausible, unsafe, incoherent, unreadable, or execution-breaking work.",
        "Every issue MUST include blocking=true or blocking=false.",
        "Set blocking=true only when the current artifact is not commercially strong enough to advance to the next department without another generation at this same stage.",
        "A blocking issue must be material: it must compromise brief fidelity, causal/narrative coherence, distinctive authorship, commercial legibility, continuity, physical/execution feasibility, safety/rights, required content, or the core emotional/visual payoff.",
        "Do NOT set blocking=true merely because you can imagine a more elegant alternative, stronger polish, a different taste preference, extra nuance, or a theoretically better version.",
        "If the artifact is strong enough to advance and remaining comments are improvements rather than defects, verdict must be ACCEPT and those issues must use blocking=false.",
        "Ask the stopping question: if no further model generation were available at this stage, would a strong studio refuse to advance this artifact? If yes, mark the material defect blocking=true. If no, record it as blocking=false and advance.",
        "REJECT is reserved for fundamentally unusable or materially wrong work; REVISE requires at least one blocking issue.",
        "Perfection is not a release criterion. Commercially strong, coherent, distinctive, on-brief and executable work must advance even when optional improvements remain.",
    ]


def _explicit_blocking(issue: Any) -> bool | None:
    if not isinstance(issue, dict):
        return None
    value = issue.get("blocking")
    if isinstance(value, bool):
        return value
    return None


def _issue_change(issue: Any) -> str:
    if not isinstance(issue, dict):
        return str(issue or "").strip()
    for key in ("required_change", "repair", "detail", "finding", "issue"):
        value = str(issue.get(key) or "").strip()
        if value:
            return value
    return "Resolve the material release-blocking defect."


def calibrate_review(review: Dict[str, Any], *, stage: str) -> Dict[str, Any]:
    """Enforce a high-quality stopping rule without weakening any quality gate.

    Safety bias is intentional:
    - REJECT is never softened here.
    - A REVISE is softened to ACCEPT only when *every* issue explicitly says
      blocking=false and commercial confidence is MEDIUM/HIGH.
    - Missing blocking metadata keeps the old strict behavior (REVISE stays REVISE).
    - Any explicit blocker on an ACCEPT forces REVISE.

    This means old fixtures/providers remain at least as strict as before. Only a
    Producer that explicitly classifies its remaining criticism as advisory can stop
    an unnecessary regeneration loop.
    """
    out = deepcopy(review)
    verdict = str(out.get("verdict") or "").upper()
    issues = list(out.get("issues") or [])
    explicit = [_explicit_blocking(issue) for issue in issues]
    has_blocker = any(value is True for value in explicit)
    all_explicit_advisory = bool(issues) and all(value is False for value in explicit)
    confidence = str(out.get("commercial_confidence") or "").upper()

    if verdict == "REJECT":
        return out

    if verdict == "ACCEPT":
        if has_blocker:
            out["verdict"] = "REVISE"
            blockers = [issue for issue in issues if _explicit_blocking(issue) is True]
            changes = []
            for issue in blockers:
                change = _issue_change(issue)
                if change and change not in changes:
                    changes.append(change)
            if not str(out.get("revision_brief") or "").strip():
                out["revision_brief"] = "Resolve the material blocking issue(s): " + " ".join(changes)
            if confidence == "HIGH":
                out["commercial_confidence"] = "MEDIUM"
        return out

    if verdict == "REVISE":
        # Never soften LOW-confidence work, unknown/missing blocking metadata, or a
        # mixed review containing even one material blocker.
        if all_explicit_advisory and confidence in {"MEDIUM", "HIGH"}:
            out["verdict"] = "ACCEPT"
            out["revision_brief"] = ""
            note = str(out.get("notes") or "").strip()
            suffix = (
                f"{stage} review contained advisory improvements only; the commercial "
                "quality floor is met, so NexMind advances without another generation."
            )
            out["notes"] = (note + " " + suffix).strip()
        return out

    return out
