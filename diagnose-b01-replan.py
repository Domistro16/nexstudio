#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import traceback
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

ROOT = pathlib.Path(__file__).resolve().parent


def load_env(path: pathlib.Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key or any(ch.isspace() for ch in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _unique_strings(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for value in values:
        text = _text(value)
        if text and text not in out:
            out.append(text)
    return out


def _decision_payload(result: Dict[str, Any], slot: str) -> Dict[str, Any]:
    state = ((result.get("checkpoint") or {}).get("state") or {})
    decision = ((state.get("decisions") or {}).get(slot) or {})
    payload = decision.get("payload")
    return deepcopy(payload) if isinstance(payload, dict) else {}


def _story_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    story = result.get("story")
    if isinstance(story, dict) and story:
        return deepcopy(story)
    payload = _decision_payload(result, "film_thesis")
    nested = payload.get("story")
    if isinstance(nested, dict):
        return deepcopy(nested)
    return payload


def _review_index(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    state = ((result.get("checkpoint") or {}).get("state") or {})
    index: Dict[str, Dict[str, Any]] = {}
    for key in (
        "producer_reviews",
        "p3_reviews",
        "p45_reviews",
        "p6_reviews",
        "p7_reviews",
        "final_producer_reviews",
    ):
        for record in state.get(key) or []:
            if not isinstance(record, dict):
                continue
            review_id = str(record.get("review_id") or "")
            if review_id:
                index[review_id] = deepcopy(record)
    return index


def _committed_stage_reviews(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    state = ((result.get("checkpoint") or {}).get("state") or {})
    decisions = state.get("decisions") or {}
    review_index = _review_index(result)
    out: Dict[str, Dict[str, Any]] = {}
    for slot, decision in decisions.items():
        if not isinstance(decision, dict):
            continue
        review_id = str(decision.get("producer_review_id") or "")
        record = review_index.get(review_id)
        if record and isinstance(record.get("review"), dict):
            out[str(slot)] = deepcopy(record["review"])
    return out


def _collect_review_notes(stage_reviews: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    advisory: List[Dict[str, Any]] = []
    blocking: List[Dict[str, Any]] = []
    validations: List[Dict[str, Any]] = []
    for stage, review in stage_reviews.items():
        for issue in review.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            item = {"stage": stage, **deepcopy(issue)}
            if issue.get("blocking") is False:
                advisory.append(item)
            elif issue.get("blocking") is True:
                blocking.append(item)
        for item in review.get("deferred_production_validations") or []:
            if isinstance(item, dict):
                validations.append({"stage": stage, **deepcopy(item)})
            else:
                validations.append({"stage": stage, "detail": _text(item)})
    return {"advisory": advisory, "blocking": blocking, "validations": validations}


def _rational_seconds(value: Any) -> Optional[float]:
    if not isinstance(value, dict):
        return None
    try:
        raw = float(value.get("value"))
        rate = float(value.get("rate"))
        if rate <= 0:
            return None
        return raw / rate
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _seconds_label(value: Any) -> str:
    seconds = _rational_seconds(value)
    if seconds is None:
        return ""
    return f"{seconds:.2f}s"


def _compact_camera(camera: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(camera, dict):
        return {}
    atom = camera.get("camera_atom") if isinstance(camera.get("camera_atom"), dict) else {}
    return {
        "idiom": camera.get("idiom"),
        "shot_scale": camera.get("shot_scale"),
        "angle": camera.get("angle"),
        "subject_target": camera.get("subject_target"),
        "reveal_framing": camera.get("reveal_framing"),
        "depth_strategy": camera.get("depth_strategy"),
        "camera_move": atom.get("atom"),
        "camera_target": atom.get("target"),
        "camera_motivation": atom.get("motivation"),
        "transition_relation": camera.get("transition_relation"),
        "continuity_reason": camera.get("continuity_reason"),
    }


def _compact_editorial(editorial: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(editorial, dict):
        return {}
    start_seconds = _rational_seconds(editorial.get("start"))
    duration_seconds = _rational_seconds(editorial.get("duration"))
    end_seconds = None if start_seconds is None or duration_seconds is None else start_seconds + duration_seconds
    return {
        "role": editorial.get("role"),
        "start_seconds": start_seconds,
        "duration_seconds": duration_seconds,
        "end_seconds": end_seconds,
        "energy": editorial.get("energy"),
        "transition": editorial.get("transition"),
        "stillness_frames": editorial.get("stillness_frames"),
        "duration_rationale": editorial.get("duration_rationale"),
    }


def _compact_motion(actions: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        execution = action.get("execution") if isinstance(action.get("execution"), dict) else {}
        out.append({
            "action_id": action.get("action_id"),
            "actor": action.get("actor"),
            "semantic_action": action.get("semantic_action"),
            "requested_verb": action.get("requested_verb"),
            "target": action.get("target"),
            "prop": action.get("prop"),
            "motivation": action.get("motivation"),
            "settle": action.get("settle"),
            "contact_requirement": action.get("contact_requirement"),
            "execution_status": execution.get("status"),
            "resolved_verb": execution.get("resolved_verb"),
        })
    return out


def _compact_sound(events: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        out.append({
            "event_id": event.get("event_id"),
            "kind": event.get("kind"),
            "semantic_tag": event.get("semantic_tag"),
            "intensity": event.get("intensity"),
            "narrative_reason": event.get("narrative_reason"),
            "sync_target": event.get("sync_target"),
            "resource_status": resource.get("status"),
            "asset_id": resource.get("asset_id"),
        })
    return out


def build_creative_review(diagnostic: Dict[str, Any]) -> Dict[str, Any]:
    """Create a deterministic, human-readable creative review from committed P8 state.

    This function performs no model calls and makes no new creative decisions. It only
    reorganizes already-committed NexMind decisions and Producer reviews.
    """
    brief = deepcopy(diagnostic.get("brief") or {})
    result = deepcopy(diagnostic.get("result") or {})
    state = ((result.get("checkpoint") or {}).get("state") or {})
    decisions = state.get("decisions") or {}
    story = _story_from_result(result)
    thesis = story.get("film_thesis") if isinstance(story.get("film_thesis"), dict) else {}
    final_board = result.get("finalBoard") if isinstance(result.get("finalBoard"), dict) else {}
    stage_reviews = _committed_stage_reviews(result)
    review_notes = _collect_review_notes(stage_reviews)

    beats: List[Dict[str, Any]] = []
    for index, beat in enumerate(final_board.get("beats") or []):
        if not isinstance(beat, dict):
            continue
        visual_direction = beat.get("visual_direction") if isinstance(beat.get("visual_direction"), dict) else {}
        visual_treatment = visual_direction.get("beat_treatment") if isinstance(visual_direction.get("beat_treatment"), dict) else {}
        art = beat.get("art_direction") if isinstance(beat.get("art_direction"), dict) else {}
        audience = beat.get("audience_state_change") if isinstance(beat.get("audience_state_change"), dict) else {}
        editorial = _compact_editorial(beat.get("editorial") or {})
        beats.append({
            "order": index + 1,
            "beat_id": beat.get("beat_id") or f"BEAT_{index + 1}",
            "time": {
                "start_seconds": editorial.get("start_seconds"),
                "duration_seconds": editorial.get("duration_seconds"),
                "end_seconds": editorial.get("end_seconds"),
            },
            "story": {
                "scene_thesis": beat.get("scene_thesis"),
                "audience_before": audience.get("before"),
                "audience_after": audience.get("after"),
                "opening_state": beat.get("opening_state"),
                "hero_key_state": beat.get("hero_key_state"),
                "critical_action_states": deepcopy(beat.get("critical_action_states") or []),
                "settled_state": beat.get("settled_state"),
                "narration_mode": beat.get("narration_mode"),
                "narration_text": beat.get("narration_text"),
                "narration_purpose": beat.get("narration_purpose"),
            },
            "visual": {
                "representation": visual_direction.get("representation"),
                "visual_thesis": visual_direction.get("visual_thesis"),
                "hero_state": visual_treatment.get("hero_state"),
                "visual_action": visual_treatment.get("visual_action"),
                "audience_takeaway": visual_treatment.get("audience_takeaway"),
            },
            "art": {
                "art_thesis": art.get("art_thesis"),
                "focal_owner": art.get("focal_owner"),
                "settled_visual_state": art.get("settled_visual_state"),
                "composition": deepcopy(art.get("composition") or {}),
                "environment_state": art.get("environment_state"),
                "prop_specificity": art.get("prop_specificity"),
                "character_performance_state": art.get("character_performance_state"),
                "typography_role": art.get("typography_role"),
                "depth_read": art.get("depth_read"),
            },
            "camera": _compact_camera(beat.get("camera") or {}),
            "editorial": editorial,
            "motion": {
                "intent": beat.get("motion_intent"),
                "plan_status": beat.get("motion_plan_status"),
                "actions": _compact_motion(beat.get("motion_actions") or []),
            },
            "sound": {
                "intent": beat.get("sound_intent"),
                "plan_status": beat.get("sound_plan_status"),
                "summary": deepcopy(beat.get("sound_summary") or {}),
                "events": _compact_sound(beat.get("sound_events") or []),
            },
            "continuity": {
                "in": beat.get("continuity_in"),
                "out": beat.get("continuity_out"),
            },
            "capability_risks": deepcopy(beat.get("capability_risks") or []),
        })

    repair = result.get("autonomousRepair") if isinstance(result.get("autonomousRepair"), dict) else {}
    validations = []
    for item in result.get("productionValidationRequirements") or []:
        validations.append(deepcopy(item) if isinstance(item, dict) else {"detail": _text(item)})
    for item in state.get("production_validation_requirements") or []:
        candidate = deepcopy(item) if isinstance(item, dict) else {"detail": _text(item)}
        if candidate not in validations:
            validations.append(candidate)
    for item in review_notes["validations"]:
        if item not in validations:
            validations.append(item)

    visual_payload = _decision_payload(result, "visual_concept")
    art_payload = _decision_payload(result, "art_direction")
    cinema_payload = _decision_payload(result, "cinematography")
    editorial_payload = _decision_payload(result, "editorial_rhythm")
    motion_payload = _decision_payload(result, "motion_performance")
    sound_payload = _decision_payload(result, "sound_direction")

    return {
        "schema": "NexMindCreativeStoryboardReviewV1",
        "sourceAuthority": "DETERMINISTIC_VIEW_OF_COMMITTED_P8_STATE",
        "makesNewCreativeDecisions": False,
        "brief": brief,
        "run": {
            "status": result.get("status"),
            "code": result.get("code"),
            "productionId": result.get("productionId"),
            "revision": result.get("revision"),
            "stateHash": result.get("stateHash"),
            "decisionSlots": deepcopy(result.get("decisionSlots") or []),
            "renderReady": bool(result.get("renderReady")),
            "finalProducerInvoked": bool(result.get("finalProducerInvoked")),
            "creativeLockCommitted": bool(result.get("creativeLockCommitted")),
            "unresolvedDepartments": deepcopy(final_board.get("unresolved_departments") or []),
        },
        "film": {
            "central_argument": thesis.get("central_argument"),
            "film_kind": thesis.get("film_kind"),
            "audience_before": thesis.get("audience_before"),
            "audience_after": thesis.get("audience_after"),
            "hero_kind": thesis.get("hero_kind"),
            "camera_idea": thesis.get("camera_idea"),
            "opening_contract": thesis.get("opening_contract"),
            "final_payoff": thesis.get("final_payoff"),
            "tone": thesis.get("tone"),
            "emotional_trajectory": deepcopy(thesis.get("emotional_trajectory") or []),
            "visual_trajectory": deepcopy(thesis.get("visual_trajectory") or []),
            "anti_goals": deepcopy(thesis.get("anti_goals") or []),
            "story_notes": deepcopy(story.get("story_notes") or []),
        },
        "selectedCreativeSystem": {
            "visual_concept": deepcopy(visual_payload),
            "art_direction": deepcopy(art_payload.get("art_direction") or art_payload),
            "form_resolution": deepcopy(art_payload.get("form_resolution") or {}),
            "cinematography": deepcopy(cinema_payload.get("cinematography") or cinema_payload),
            "editorial_rhythm": deepcopy(editorial_payload.get("editorial_rhythm") or editorial_payload),
            "motion_performance": deepcopy(motion_payload.get("motion_performance") or motion_payload),
            "sound_direction": deepcopy(sound_payload.get("sound_direction") or sound_payload),
        },
        "beats": beats,
        "producerAssessments": deepcopy(stage_reviews),
        "nonBlockingCreativeNotes": review_notes["advisory"],
        "blockingIssuesOnCommittedWork": review_notes["blocking"],
        "productionValidationRequirements": validations,
        "attempts": {
            "currentLineage": deepcopy(repair.get("attempts") or {}),
            "lifetime": deepcopy(repair.get("lifetime_attempts") or {}),
            "repairLedgerEntries": len(repair.get("ledger") or []),
            "broaderStrategyReplans": len(repair.get("broader_strategy_replans") or []),
        },
        "providerPerformance": deepcopy(result.get("providerPerformance") or {}),
    }


def _md_value(value: Any) -> str:
    text = _text(value)
    return text if text else "—"


def _md_bullets(values: Iterable[Any], indent: str = "") -> List[str]:
    lines: List[str] = []
    for value in values:
        text = _text(value)
        if text:
            lines.append(f"{indent}- {text}")
    return lines


def _issue_label(issue: Dict[str, Any]) -> str:
    area = _text(issue.get("area") or issue.get("code") or issue.get("stage") or "Creative note")
    finding = _text(issue.get("finding") or issue.get("issue") or issue.get("detail") or issue.get("required_change") or "")
    required = _text(issue.get("required_change") or issue.get("repair") or "")
    text = f"**{area}:** {finding}" if finding else f"**{area}**"
    if required and required != finding:
        text += f"  \n  *Possible improvement:* {required}"
    return text


def render_creative_review_markdown(review: Dict[str, Any]) -> str:
    brief = review.get("brief") or {}
    run = review.get("run") or {}
    film = review.get("film") or {}
    system = review.get("selectedCreativeSystem") or {}
    lines: List[str] = []

    lines += [
        f"# {brief.get('id') or 'NexMind'} — Creative Storyboard Review",
        "",
        "> Deterministic presentation of NexMind's committed P8 creative state. This file makes **no new creative decisions** and performs **no additional model calls**.",
        "",
        "## Run status",
        "",
        f"- **Status:** {_md_value(run.get('status'))}",
        f"- **Code:** {_md_value(run.get('code'))}",
        f"- **Family:** {_md_value(brief.get('family'))}",
        f"- **Domain:** {_md_value(brief.get('domain'))}",
        f"- **Render ready:** {_md_value(run.get('renderReady'))}",
        f"- **Final Producer invoked:** {_md_value(run.get('finalProducerInvoked'))}",
        f"- **Creative Lock committed:** {_md_value(run.get('creativeLockCommitted'))}",
        f"- **State hash:** `{_md_value(run.get('stateHash'))}`",
        "",
        "## Customer brief",
        "",
        _md_value(brief.get("brief")),
        "",
        "## Film idea",
        "",
        f"**Central argument:** {_md_value(film.get('central_argument'))}",
        "",
        f"**Film kind:** {_md_value(film.get('film_kind'))}",
        "",
        f"**Audience before → after:** {_md_value(film.get('audience_before'))} → {_md_value(film.get('audience_after'))}",
        "",
        f"**Hero:** {_md_value(film.get('hero_kind'))}",
        "",
        f"**Opening contract:** {_md_value(film.get('opening_contract'))}",
        "",
        f"**Final payoff:** {_md_value(film.get('final_payoff'))}",
        "",
        f"**Governing camera idea:** {_md_value(film.get('camera_idea'))}",
        "",
    ]

    if film.get("emotional_trajectory"):
        lines += ["### Emotional trajectory", ""] + _md_bullets(film["emotional_trajectory"]) + [""]
    if film.get("visual_trajectory"):
        lines += ["### Visual trajectory", ""] + _md_bullets(film["visual_trajectory"]) + [""]
    if film.get("anti_goals"):
        lines += ["### Anti-goals", ""] + _md_bullets(film["anti_goals"]) + [""]

    visual = system.get("visual_concept") if isinstance(system.get("visual_concept"), dict) else {}
    art = system.get("art_direction") if isinstance(system.get("art_direction"), dict) else {}
    cinema = system.get("cinematography") if isinstance(system.get("cinematography"), dict) else {}
    editorial = system.get("editorial_rhythm") if isinstance(system.get("editorial_rhythm"), dict) else {}
    motion = system.get("motion_performance") if isinstance(system.get("motion_performance"), dict) else {}
    sound = system.get("sound_direction") if isinstance(system.get("sound_direction"), dict) else {}

    lines += [
        "## Selected creative system",
        "",
        f"**Visual concept:** {_md_value(visual.get('visual_thesis'))}",
        "",
        f"**Visual transformation:** {_md_value(visual.get('transformation'))}",
        "",
        f"**Visual hero:** {_md_value(visual.get('hero_kind'))}",
        "",
        f"**Art thesis:** {_md_value(art.get('art_thesis') or art.get('visual_thesis'))}",
        "",
        f"**Art composition:** {_md_value((art.get('composition') or {}).get('archetype') if isinstance(art.get('composition'), dict) else '')}",
        "",
        f"**Cinematography thesis:** {_md_value(cinema.get('cinema_thesis') or cinema.get('visual_thesis'))}",
        "",
        f"**Editorial thesis:** {_md_value(editorial.get('editorial_thesis') or editorial.get('visual_thesis'))}",
        "",
        f"**Motion thesis:** {_md_value(motion.get('motion_thesis') or motion.get('visual_thesis'))}",
        "",
        f"**Sound thesis:** {_md_value(sound.get('sound_thesis') or sound.get('visual_thesis'))}",
        "",
    ]

    lines += ["# Beat-by-beat storyboard", ""]
    if not review.get("beats"):
        lines += ["No integrated final-board beats are available yet. The run may have stopped before `DEPARTMENTS_COMPLETE`.", ""]
    for beat in review.get("beats") or []:
        time_info = beat.get("time") or {}
        start = time_info.get("start_seconds")
        end = time_info.get("end_seconds")
        duration = time_info.get("duration_seconds")
        timing = ""
        if start is not None and end is not None:
            timing = f" — {start:.2f}s–{end:.2f}s ({duration:.2f}s)"
        lines += [
            f"## {beat.get('order'):02d}. {beat.get('beat_id')}{timing}",
            "",
            f"**Narrative purpose / scene thesis:** {_md_value((beat.get('story') or {}).get('scene_thesis'))}",
            "",
            f"**Audience before → after:** {_md_value((beat.get('story') or {}).get('audience_before'))} → {_md_value((beat.get('story') or {}).get('audience_after'))}",
            "",
            f"**Opening state:** {_md_value((beat.get('story') or {}).get('opening_state'))}",
            "",
            f"**Hero state:** {_md_value((beat.get('story') or {}).get('hero_key_state'))}",
            "",
        ]
        actions = (beat.get("story") or {}).get("critical_action_states") or []
        if actions:
            lines += ["**Critical action states:**", ""] + _md_bullets(actions) + [""]
        lines += [
            f"**Settled/payoff state:** {_md_value((beat.get('story') or {}).get('settled_state'))}",
            "",
            f"**Visual action:** {_md_value((beat.get('visual') or {}).get('visual_action'))}",
            "",
            f"**Audience takeaway:** {_md_value((beat.get('visual') or {}).get('audience_takeaway'))}",
            "",
            f"**Art / settled frame:** {_md_value((beat.get('art') or {}).get('settled_visual_state'))}",
            "",
        ]
        camera = beat.get("camera") or {}
        lines += [
            "### Camera",
            "",
            f"- **Shot:** {_md_value(camera.get('shot_scale'))}, {_md_value(camera.get('angle'))}",
            f"- **Subject:** {_md_value(camera.get('subject_target'))}",
            f"- **Move:** {_md_value(camera.get('camera_move'))} → {_md_value(camera.get('camera_target'))}",
            f"- **Motivation:** {_md_value(camera.get('camera_motivation'))}",
            f"- **Framing:** {_md_value(camera.get('reveal_framing'))}",
            f"- **Continuity:** {_md_value(camera.get('continuity_reason'))}",
            "",
        ]
        edit = beat.get("editorial") or {}
        lines += [
            "### Edit / rhythm",
            "",
            f"- **Role:** {_md_value(edit.get('role'))}",
            f"- **Energy:** {_md_value(edit.get('energy'))}",
            f"- **Transition:** {_md_value(edit.get('transition'))}",
            f"- **Stillness:** {_md_value(edit.get('stillness_frames'))} frames",
            f"- **Rationale:** {_md_value(edit.get('duration_rationale'))}",
            "",
        ]
        narration_mode = _md_value((beat.get("story") or {}).get("narration_mode"))
        narration_text = _md_value((beat.get("story") or {}).get("narration_text"))
        lines += [
            "### Narration",
            "",
            f"- **Mode:** {narration_mode}",
            f"- **Text:** {narration_text}",
            f"- **Purpose:** {_md_value((beat.get('story') or {}).get('narration_purpose'))}",
            "",
        ]
        motion_block = beat.get("motion") or {}
        lines += ["### Motion / performance", "", f"**Intent:** {_md_value(motion_block.get('intent'))}", ""]
        for action in motion_block.get("actions") or []:
            lines.append(
                f"- **{_md_value(action.get('action_id'))}:** {_md_value(action.get('requested_verb'))} — "
                f"{_md_value(action.get('motivation'))} (execution: {_md_value(action.get('execution_status'))})"
            )
        lines.append("")
        sound_block = beat.get("sound") or {}
        lines += ["### Sound", "", f"**Intent:** {_md_value(sound_block.get('intent'))}", ""]
        for event in sound_block.get("events") or []:
            lines.append(
                f"- **{_md_value(event.get('kind'))} / {_md_value(event.get('semantic_tag'))}:** "
                f"{_md_value(event.get('narrative_reason'))} — sync: {_md_value(event.get('sync_target'))}"
            )
        lines += ["", "---", ""]

    lines += ["# Producer assessment", ""]
    for stage, review_item in (review.get("producerAssessments") or {}).items():
        lines += [
            f"## {stage}",
            "",
            f"- **Verdict:** {_md_value(review_item.get('verdict'))}",
            f"- **Commercial confidence:** {_md_value(review_item.get('commercial_confidence'))}",
        ]
        strengths = review_item.get("strengths") or []
        if strengths:
            lines += ["- **Strengths:**"] + [f"  - {_text(x)}" for x in strengths if _text(x)]
        lines.append("")

    lines += ["# Non-blocking creative notes", ""]
    advisory = review.get("nonBlockingCreativeNotes") or []
    if advisory:
        for issue in advisory:
            lines.append(f"- {_issue_label(issue)}")
    else:
        lines.append("- None recorded on the committed work.")
    lines.append("")

    blockers = review.get("blockingIssuesOnCommittedWork") or []
    lines += ["# Blocking issues on committed work", ""]
    if blockers:
        for issue in blockers:
            lines.append(f"- {_issue_label(issue)}")
    else:
        lines.append("- None. This is the expected state for committed departments.")
    lines.append("")

    validations = review.get("productionValidationRequirements") or []
    lines += ["# Production validations", ""]
    if validations:
        for item in validations:
            if isinstance(item, dict):
                stage = _text(item.get("stage"))
                detail = _text(item.get("detail") or item.get("required_change") or item.get("finding") or item)
                prefix = f"**{stage}:** " if stage else ""
                lines.append(f"- {prefix}{detail}")
            else:
                lines.append(f"- {_text(item)}")
    else:
        lines.append("- None recorded.")
    lines.append("")

    attempts = review.get("attempts") or {}
    lines += [
        "# Run economy",
        "",
        f"- **Current-lineage attempts:** `{json.dumps(attempts.get('currentLineage') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- **Lifetime attempts:** `{json.dumps(attempts.get('lifetime') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- **Repair ledger entries:** {_md_value(attempts.get('repairLedgerEntries'))}",
        f"- **Broader strategy replans:** {_md_value(attempts.get('broaderStrategyReplans'))}",
        "",
        "## Review boundary",
        "",
        "This artifact reviews the **creative brain/pre-render storyboard state**. It is not proof of final encoded-film quality. Exact-media Final Producer and independent perceptual review occur only after rendering.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_creative_artifacts(diagnostic: Dict[str, Any], reports: pathlib.Path) -> Dict[str, pathlib.Path]:
    brief_id = str((diagnostic.get("brief") or {}).get("id") or "B01")
    creative = build_creative_review(diagnostic)
    json_path = reports / f"{brief_id}_CREATIVE_STORYBOARD_REVIEW.json"
    md_path = reports / f"{brief_id}_CREATIVE_STORYBOARD_REVIEW.md"
    json_path.write_text(json.dumps(creative, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_creative_review_markdown(creative), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def print_replan_summary(result: Dict[str, Any]) -> None:
    print("\n=== REPLAN SUMMARY ===")
    print("status:", result.get("status"))
    print("code:", result.get("code"))
    print("department:", result.get("department"))
    print("attempts:", result.get("attempts"), "/", result.get("maxAttempts"))

    rr = result.get("repairRequest") or {}
    print("owner_department:", rr.get("owner_department"))
    print("source_department:", rr.get("source_department"))
    print("invalidate_slots:", rr.get("invalidate_slots"))
    print("quality_reasons:", json.dumps(rr.get("quality_reasons") or [], indent=2, ensure_ascii=False))
    print("issues:", json.dumps(rr.get("issues") or [], indent=2, ensure_ascii=False))
    print("revision_plan:", json.dumps(rr.get("revision_plan") or [], indent=2, ensure_ascii=False))

    repair = result.get("autonomousRepair") or {}
    print("\nattempt_limits_by_department:", json.dumps(repair.get("attempt_limits_by_department") or {}, indent=2))
    print("attempts_by_department:", json.dumps(repair.get("attempts") or {}, indent=2))
    print("lifetime_attempts:", json.dumps(repair.get("lifetime_attempts") or {}, indent=2))
    ledger = repair.get("ledger") or []
    print("last_repair_ledger_entries:", json.dumps(ledger[-8:], indent=2, ensure_ascii=False))

    performance = result.get("providerPerformance") or {}
    print("\nprovider_performance:", json.dumps(performance, indent=2, ensure_ascii=False))
    audits = result.get("providerAudits") or []
    print("\nlast_provider_audits:", json.dumps(audits[-12:], indent=2, ensure_ascii=False))


def run_live_diagnostic(brief_id: str) -> Dict[str, Any]:
    load_env(ROOT / ".env")
    sys.path.insert(0, str(ROOT / "services" / "studio-nexmind-p8"))
    from orchestrator import run_full_p8, classify_exception

    brief_file = ROOT / "evaluations" / "nexmind-p8-commercial-brain-v2" / "BLIND_COMMERCIAL_BRIEFS_V2.json"
    data = json.loads(brief_file.read_text(encoding="utf-8"))
    brief = next((b for b in data["briefs"] if b["id"] == brief_id), None)
    if not brief:
        raise SystemExit(f"Brief {brief_id!r} not found")

    families = ["EXPLAINER", "WHITEBOARD", "STICKMAN", "EDITORIAL_MOTION"]
    idx = data["briefs"].index(brief)
    family = families[idx % 4]

    events: List[Dict[str, Any]] = []

    def progress(phase: str, payload: Dict[str, Any]) -> None:
        item = {"phase": phase, "payload": payload}
        events.append(item)
        print(f"{brief['id']} phase={phase} payload={json.dumps(payload, ensure_ascii=False)}", flush=True)

    req = {
        "schema": "StudioNexMindP8RequestV1",
        "productionId": f"diagnostic-{brief['id']}",
        "workflowRunId": f"diag-{brief['id']}",
        "projectVersion": 1,
        "family": family,
        "videoType": "blind-commercial-eval",
        "prompt": brief["brief"],
        "planPreview": None,
        "sourceSummaries": [],
        "evidence": [{
            "claim_id": "USER-BRIEF-1",
            "claim": brief["brief"],
            "source": "sealed-blind-brief",
            "status": "USER_SUPPLIED",
        }],
        "durationSeconds": brief["duration_seconds"],
        "aspectRatio": "16:9",
        "voicePreference": None,
        "brandContext": None,
        "creativeMemory": [],
        "policy": {
            "fullNexMindRequired": True,
            "planPreviewIsNotCreativeLock": True,
        },
    }

    started = time.perf_counter()
    caught_exception: Optional[Dict[str, str]] = None
    try:
        result = run_full_p8(req, progress=progress)
    except Exception as exc:  # keep diagnostic evidence if a local bug escapes orchestration
        caught_exception = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        result = classify_exception(exc)
    elapsed = round(time.perf_counter() - started, 3)

    out = {
        "brief": {
            "id": brief["id"],
            "family": family,
            "domain": brief.get("domain"),
            "brief": brief["brief"],
            "duration_seconds": brief.get("duration_seconds"),
        },
        "elapsedSeconds": elapsed,
        "events": events,
        "result": result,
        "exception": caught_exception,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the NexMind B01 replan diagnostic and also emit a deterministic, "
            "human-readable creative storyboard review from the committed P8 state."
        )
    )
    parser.add_argument("--brief", default="B01")
    parser.add_argument(
        "--render-existing",
        metavar="PATH",
        help="Do not call a provider. Re-render creative review files from an existing diagnostic JSON.",
    )
    args = parser.parse_args()

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    if args.render_existing:
        source_path = pathlib.Path(args.render_existing)
        if not source_path.is_absolute():
            source_path = (ROOT / source_path).resolve()
        diagnostic = json.loads(source_path.read_text(encoding="utf-8"))
        artifacts = write_creative_artifacts(diagnostic, reports)
        print("CREATIVE REVIEW JSON:", artifacts["json"])
        print("CREATIVE REVIEW MARKDOWN:", artifacts["markdown"])
        return 0

    diagnostic = run_live_diagnostic(args.brief)
    result = diagnostic.get("result") or {}
    out_path = reports / f"{args.brief}_BROADER_REPLAN_DIAGNOSTIC.json"
    # Deliberately strict: if the result itself contains a non-JSON internal object,
    # fail here rather than silently hiding another serialization boundary defect.
    out_path.write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False), encoding="utf-8")

    print_replan_summary(result)
    artifacts = write_creative_artifacts(diagnostic, reports)

    print("\nelapsed_seconds:", diagnostic.get("elapsedSeconds"))
    if diagnostic.get("exception"):
        print("escaped_exception:", json.dumps(diagnostic["exception"], indent=2, ensure_ascii=False))
    print("\nFULL DIAGNOSTIC:", out_path)
    print("CREATIVE REVIEW JSON:", artifacts["json"])
    print("CREATIVE REVIEW MARKDOWN:", artifacts["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
