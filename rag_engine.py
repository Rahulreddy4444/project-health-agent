"""
RAG Scoring Engine

Implements the 5-dimension weighted RAG framework defined in the methodology.
Each dimension is scored independently, then combined into a composite score
with override rules applied.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

import config


# ─── Score Constants ─────────────────────────────────────────────────────────

GREEN = 3
AMBER = 2
RED = 1

SCORE_TO_LABEL = {GREEN: "Green", AMBER: "Amber", RED: "Red"}
LABEL_TO_SCORE = {"Green": GREEN, "Amber": AMBER, "Red": RED}


def _get_active_tasks(tasks: List[Dict]) -> List[Dict]:
    """Filter to active tasks (exclude Not Applicable, On Hold, and empty)."""
    return [
        t for t in tasks
        if t.get("status") not in ("Not Applicable", "On Hold", "Unknown", "")
        and not t.get("not_applicable")
        and not t.get("on_hold")
        and t.get("task_name", "").strip()
    ]


def _get_milestone_tasks(tasks: List[Dict]) -> List[Dict]:
    """Get milestone/phase-level tasks (Level 0-1 or has Phase/Milestone value)."""
    return [
        t for t in tasks
        if t.get("phase_milestone") is not None
        or (t.get("level") is not None and t["level"] <= 1)
    ]


def _get_due_tasks(tasks: List[Dict], reference_date: datetime) -> List[Dict]:
    """Get tasks that should be complete by the reference date."""
    return [
        t for t in tasks
        if t.get("end_date") is not None and t["end_date"] <= reference_date
    ]


# ─── Dimension 1: Schedule Adherence ────────────────────────────────────────

def score_schedule_adherence(tasks: List[Dict], summary: Dict) -> Dict[str, Any]:
    """
    Score schedule adherence based on variance between planned and actual dates.
    
    Uses variance_days field (negative = late).
    Falls back to comparing baseline vs actual dates.
    """
    result = {
        "dimension": "Schedule Adherence",
        "weight": config.WEIGHTS["schedule_adherence"],
        "score": None,
        "label": "Unknown",
        "reasoning": "",
        "metrics": {},
    }
    
    # Collect variance data
    variances = []
    for task in _get_active_tasks(tasks):
        v = task.get("variance_days")
        if v is not None:
            variances.append(v)
        elif task.get("baseline_finish") and task.get("end_date"):
            # Calculate variance: baseline_finish - end_date (positive = early, negative = late)
            delta = (task["baseline_finish"] - task["end_date"]).days
            variances.append(delta)
    
    if not variances:
        result["reasoning"] = "No baseline or variance data available. Cannot assess schedule adherence."
        result["metrics"]["data_available"] = False
        return result
    
    # Negative variance = late; we want absolute lateness
    late_variances = [abs(v) for v in variances if v < 0]
    avg_lateness = sum(late_variances) / len(late_variances) if late_variances else 0
    pct_late = len(late_variances) / len(variances)
    
    result["metrics"] = {
        "total_tasks_with_variance": len(variances),
        "late_tasks": len(late_variances),
        "pct_late": round(pct_late * 100, 1),
        "avg_lateness_days": round(avg_lateness, 1),
        "max_lateness_days": round(max(late_variances), 1) if late_variances else 0,
        "data_available": True,
    }
    
    # Score
    if avg_lateness <= config.SCHEDULE_VARIANCE_GREEN_MAX_DAYS and pct_late < config.SCHEDULE_LATE_TASKS_GREEN_MAX_PCT:
        result["score"] = GREEN
        result["label"] = "Green"
        result["reasoning"] = (
            f"Schedule adherence is strong. Average delay is only {avg_lateness:.1f} days "
            f"and just {pct_late*100:.0f}% of tasks with variance data are running late."
        )
    elif avg_lateness <= config.SCHEDULE_VARIANCE_AMBER_MAX_DAYS or pct_late < config.SCHEDULE_LATE_TASKS_AMBER_MAX_PCT:
        result["score"] = AMBER
        result["label"] = "Amber"
        result["reasoning"] = (
            f"Schedule is under pressure. Average delay is {avg_lateness:.1f} days "
            f"with {pct_late*100:.0f}% of baselined tasks running late. "
            f"Maximum single-task delay is {result['metrics']['max_lateness_days']} days."
        )
    else:
        result["score"] = RED
        result["label"] = "Red"
        result["reasoning"] = (
            f"Schedule is significantly slipping. Average delay is {avg_lateness:.1f} days "
            f"with {pct_late*100:.0f}% of tasks running behind baseline. "
            f"Maximum delay reaches {result['metrics']['max_lateness_days']} days."
        )
    
    return result


# ─── Dimension 2: Completion Progress ───────────────────────────────────────

def score_completion_progress(tasks: List[Dict], summary: Dict) -> Dict[str, Any]:
    """
    Score completion progress by comparing actual % complete against expected
    progress based on elapsed time.
    """
    result = {
        "dimension": "Completion Progress",
        "weight": config.WEIGHTS["completion_progress"],
        "score": None,
        "label": "Unknown",
        "reasoning": "",
        "metrics": {},
    }
    
    # Get project timeline from summary
    start = summary.get("project_start")
    end = summary.get("project_end")
    today = summary.get("todays_date") or datetime.now()
    actual_pct = summary.get("percent_complete")
    
    if not all([start, end, actual_pct is not None]):
        # Fallback: calculate from tasks
        active = _get_active_tasks(tasks)
        if active:
            completed = [t for t in active if t.get("status") == "Completed"]
            actual_pct = len(completed) / len(active)
            # Get earliest start and latest end
            starts = [t["start_date"] for t in active if t.get("start_date")]
            ends = [t["end_date"] for t in active if t.get("end_date")]
            if starts and ends:
                start = min(starts)
                end = max(ends)
        
        if not all([start, end, actual_pct is not None]):
            result["reasoning"] = "Insufficient data to assess completion progress."
            result["metrics"]["data_available"] = False
            return result
    
    total_duration = (end - start).days
    elapsed = (today - start).days
    
    if total_duration <= 0:
        result["reasoning"] = "Project duration is zero or negative — cannot compute progress."
        return result
    
    expected_pct = min(elapsed / total_duration, 1.0)
    progress_ratio = actual_pct / expected_pct if expected_pct > 0 else 1.0
    
    result["metrics"] = {
        "actual_pct_complete": round(actual_pct * 100 if actual_pct <= 1 else actual_pct, 1),
        "expected_pct_complete": round(expected_pct * 100, 1),
        "progress_ratio": round(progress_ratio, 2),
        "elapsed_days": elapsed,
        "total_duration_days": total_duration,
        "days_remaining": total_duration - elapsed,
        "data_available": True,
    }
    
    # Also count task-level completion
    active = _get_active_tasks(tasks)
    completed_tasks = [t for t in active if t.get("status") == "Completed"]
    not_started = [t for t in active if t.get("status") == "Not Started"]
    
    result["metrics"]["total_active_tasks"] = len(active)
    result["metrics"]["completed_tasks"] = len(completed_tasks)
    result["metrics"]["not_started_tasks"] = len(not_started)
    result["metrics"]["in_progress_tasks"] = len(active) - len(completed_tasks) - len(not_started)
    
    # Score
    if progress_ratio >= config.COMPLETION_GREEN_RATIO:
        result["score"] = GREEN
        result["label"] = "Green"
        result["reasoning"] = (
            f"Project is tracking well. At {result['metrics']['actual_pct_complete']:.0f}% complete "
            f"vs {result['metrics']['expected_pct_complete']:.0f}% expected based on timeline. "
            f"{len(completed_tasks)} of {len(active)} active tasks are done."
        )
    elif progress_ratio >= config.COMPLETION_AMBER_RATIO:
        result["score"] = AMBER
        result["label"] = "Amber"
        gap = result["metrics"]["expected_pct_complete"] - result["metrics"]["actual_pct_complete"]
        result["reasoning"] = (
            f"Progress is lagging by ~{gap:.0f} percentage points. "
            f"Actual completion is {result['metrics']['actual_pct_complete']:.0f}% vs "
            f"{result['metrics']['expected_pct_complete']:.0f}% expected. "
            f"{len(not_started)} tasks have not yet started with "
            f"{result['metrics']['days_remaining']} days remaining."
        )
    else:
        result["score"] = RED
        result["label"] = "Red"
        gap = result["metrics"]["expected_pct_complete"] - result["metrics"]["actual_pct_complete"]
        result["reasoning"] = (
            f"Project is significantly behind schedule. At only {result['metrics']['actual_pct_complete']:.0f}% "
            f"complete vs {result['metrics']['expected_pct_complete']:.0f}% expected — a {gap:.0f}pp gap. "
            f"{len(not_started)} tasks haven't started and only {result['metrics']['days_remaining']} "
            f"days remain."
        )
    
    return result


# ─── Dimension 3: Milestone Health ──────────────────────────────────────────

def score_milestone_health(tasks: List[Dict], summary: Dict) -> Dict[str, Any]:
    """
    Score the health of milestones and phase-level tasks.
    """
    result = {
        "dimension": "Milestone Health",
        "weight": config.WEIGHTS["milestone_health"],
        "score": None,
        "label": "Unknown",
        "reasoning": "",
        "metrics": {},
    }
    
    milestones = _get_milestone_tasks(tasks)
    milestones = [m for m in milestones if not m.get("not_applicable") and not m.get("on_hold")]
    
    if not milestones:
        result["reasoning"] = "No milestone/phase-level tasks identified in the project plan."
        result["metrics"]["data_available"] = False
        return result
    
    today = summary.get("todays_date") or datetime.now()
    
    # Categorize milestones
    completed = [m for m in milestones if m.get("status") == "Completed"]
    due_milestones = _get_due_tasks(milestones, today)
    
    on_track = []
    at_risk_milestones = []
    red_milestones = []
    
    for m in milestones:
        health = m.get("schedule_health") or m.get("rag")
        if health == "Red":
            red_milestones.append(m)
        elif health == "Amber":
            at_risk_milestones.append(m)
        elif m.get("status") == "Completed":
            on_track.append(m)
        elif health == "Green":
            on_track.append(m)
        else:
            # No health indicator — check if it's overdue
            if m.get("end_date") and m["end_date"] < today and m.get("status") != "Completed":
                red_milestones.append(m)
            else:
                on_track.append(m)
    
    total = len(milestones)
    on_track_pct = len(on_track) / total if total > 0 else 0
    
    result["metrics"] = {
        "total_milestones": total,
        "completed": len(completed),
        "on_track": len(on_track),
        "at_risk": len(at_risk_milestones),
        "red": len(red_milestones),
        "on_track_pct": round(on_track_pct * 100, 1),
        "milestone_names_at_risk": [m.get("task_name", "Unknown") for m in at_risk_milestones],
        "milestone_names_red": [m.get("task_name", "Unknown") for m in red_milestones],
        "data_available": True,
    }
    
    # Score
    has_red = len(red_milestones) > 0
    has_amber = len(at_risk_milestones) > 0
    
    if on_track_pct >= config.MILESTONE_GREEN_ON_TRACK_PCT and not has_red:
        result["score"] = GREEN
        result["label"] = "Green"
        result["reasoning"] = (
            f"Milestones are healthy. {len(on_track)}/{total} milestones "
            f"({on_track_pct*100:.0f}%) are on track with {len(completed)} completed."
        )
    elif on_track_pct >= config.MILESTONE_AMBER_ON_TRACK_PCT or has_amber:
        result["score"] = AMBER
        result["label"] = "Amber"
        risk_names = result["metrics"]["milestone_names_at_risk"][:3]
        result["reasoning"] = (
            f"Some milestones need attention. {on_track_pct*100:.0f}% are on track, "
            f"but {len(at_risk_milestones)} are at risk"
            f"{' (' + ', '.join(risk_names) + ')' if risk_names else ''}."
        )
    else:
        result["score"] = RED
        result["label"] = "Red"
        red_names = result["metrics"]["milestone_names_red"][:3]
        result["reasoning"] = (
            f"Milestones are in poor health. Only {on_track_pct*100:.0f}% are on track. "
            f"{len(red_milestones)} milestones are red"
            f"{' (' + ', '.join(red_names) + ')' if red_names else ''}."
        )
    
    return result


# ─── Dimension 4: Task Risk Profile ─────────────────────────────────────────

def score_task_risk_profile(tasks: List[Dict], summary: Dict) -> Dict[str, Any]:
    """
    Analyze the distribution of task health across the project.
    """
    result = {
        "dimension": "Task Risk Profile",
        "weight": config.WEIGHTS["task_risk_profile"],
        "score": None,
        "label": "Unknown",
        "reasoning": "",
        "metrics": {},
    }
    
    active = _get_active_tasks(tasks)
    active = [t for t in active if t.get("status") != "Completed"]
    
    if not active:
        result["score"] = GREEN
        result["label"] = "Green"
        result["reasoning"] = "All active tasks are completed — no risk in the remaining task pool."
        result["metrics"]["data_available"] = True
        return result
    
    # Categorize by health
    green_count = 0
    amber_count = 0
    red_count = 0
    unknown_count = 0
    
    today = summary.get("todays_date") or datetime.now()
    
    for task in active:
        health = task.get("schedule_health") or task.get("rag")
        
        if health == "Green":
            green_count += 1
        elif health == "Amber":
            amber_count += 1
        elif health == "Red":
            red_count += 1
        else:
            # Infer health from dates if no explicit health field
            if task.get("end_date") and task["end_date"] < today:
                red_count += 1  # Overdue
            elif task.get("end_date") and (task["end_date"] - today).days < 7:
                amber_count += 1  # Due within a week
            else:
                unknown_count += 1
    
    total = len(active)
    green_pct = green_count / total
    red_pct = red_count / total
    amber_pct = amber_count / total
    
    result["metrics"] = {
        "total_active_incomplete": total,
        "green": green_count,
        "amber": amber_count,
        "red": red_count,
        "unknown": unknown_count,
        "green_pct": round(green_pct * 100, 1),
        "amber_pct": round(amber_pct * 100, 1),
        "red_pct": round(red_pct * 100, 1),
        "data_available": True,
    }
    
    # Score
    if green_pct >= config.TASK_RISK_GREEN_HEALTHY_PCT and red_pct < config.TASK_RISK_GREEN_RED_MAX_PCT:
        result["score"] = GREEN
        result["label"] = "Green"
        result["reasoning"] = (
            f"Task risk profile is healthy. {green_pct*100:.0f}% of active tasks are Green "
            f"with only {red_pct*100:.0f}% at Red."
        )
    elif green_pct >= config.TASK_RISK_AMBER_HEALTHY_PCT and red_pct < config.TASK_RISK_AMBER_RED_MAX_PCT:
        result["score"] = AMBER
        result["label"] = "Amber"
        result["reasoning"] = (
            f"Task risk profile shows moderate concern. {green_pct*100:.0f}% of tasks are Green, "
            f"but {red_pct*100:.0f}% are Red and {amber_pct*100:.0f}% are Amber."
        )
    else:
        result["score"] = RED
        result["label"] = "Red"
        result["reasoning"] = (
            f"Task risk profile is concerning. Only {green_pct*100:.0f}% of active tasks are Green "
            f"while {red_pct*100:.0f}% are Red. Immediate attention needed on "
            f"{red_count} tasks."
        )
    
    return result


# ─── Dimension 5: Stakeholder Signals ───────────────────────────────────────

def score_stakeholder_signals(tasks: List[Dict], summary: Dict, comments: List[Dict]) -> Dict[str, Any]:
    """
    Qualitative assessment from PM comments, on-hold items, and summary indicators.
    """
    result = {
        "dimension": "Stakeholder Signals",
        "weight": config.WEIGHTS["stakeholder_signals"],
        "score": None,
        "label": "Unknown",
        "reasoning": "",
        "metrics": {},
    }
    
    # Count on-hold tasks
    on_hold = [t for t in tasks if t.get("on_hold")]
    on_hold_count = len(on_hold)
    
    # Summary health
    summary_health = summary.get("schedule_health")
    at_risk = summary.get("at_risk", "").lower()
    
    # Analyze comments for concerning language
    escalation_keywords = ['blocked', 'escalat', 'delayed', 'risk', 'impact', 'issue', 'concern',
                           'slipped', 'pushed', 'urgent', 'critical', 'miss', 'overdue']
    positive_keywords = ['completed', 'on track', 'green', 'good progress', 'ahead', 'covered']
    
    negative_signals = 0
    positive_signals = 0
    comment_texts = []
    
    for c in comments:
        text = c.get("comment_text", "").lower()
        if text:
            comment_texts.append(c.get("comment_text", ""))
            if any(kw in text for kw in escalation_keywords):
                negative_signals += 1
            if any(kw in text for kw in positive_keywords):
                positive_signals += 1
    
    # Also check task-level comments
    for t in tasks:
        if t.get("comments"):
            text = t["comments"].lower()
            if any(kw in text for kw in escalation_keywords):
                negative_signals += 1
    
    result["metrics"] = {
        "on_hold_count": on_hold_count,
        "summary_health": summary_health or "Unknown",
        "at_risk_level": at_risk or "Unknown",
        "total_comments": len(comments),
        "negative_signals": negative_signals,
        "positive_signals": positive_signals,
        "comment_excerpts": comment_texts[:5],
        "data_available": True,
    }
    
    # Score
    is_summary_red = summary_health == "Red"
    is_summary_amber = summary_health == "Amber"
    is_high_risk = at_risk in ("high", "yes", "1", "true")
    
    if (on_hold_count >= config.ON_HOLD_RED_THRESHOLD or 
        is_summary_red or 
        negative_signals >= 3):
        result["score"] = RED
        result["label"] = "Red"
        reasons = []
        if on_hold_count >= config.ON_HOLD_RED_THRESHOLD:
            reasons.append(f"{on_hold_count} tasks are on hold")
        if is_summary_red:
            reasons.append("summary health is Red")
        if negative_signals >= 3:
            reasons.append(f"{negative_signals} concerning comments found")
        result["reasoning"] = f"Stakeholder signals are negative: {'; '.join(reasons)}."
    elif (on_hold_count >= config.ON_HOLD_AMBER_THRESHOLD or 
          is_summary_amber or 
          is_high_risk or 
          negative_signals >= 1):
        result["score"] = AMBER
        result["label"] = "Amber"
        reasons = []
        if on_hold_count >= config.ON_HOLD_AMBER_THRESHOLD:
            reasons.append(f"{on_hold_count} task(s) on hold")
        if is_summary_amber:
            reasons.append("summary health is Amber")
        if is_high_risk:
            reasons.append("project flagged as High risk")
        if negative_signals >= 1:
            reasons.append(f"{negative_signals} comment(s) flag concerns")
        result["reasoning"] = f"Mixed stakeholder signals: {'; '.join(reasons)}."
    else:
        result["score"] = GREEN
        result["label"] = "Green"
        result["reasoning"] = (
            f"Stakeholder signals are positive. No tasks on hold, "
            f"summary health is {summary_health or 'not flagged'}, "
            f"and {positive_signals} positive comment(s) found."
        )
    
    return result


# ─── Composite Scoring ──────────────────────────────────────────────────────

def compute_composite_rag(dimensions: List[Dict], summary: Dict) -> Dict[str, Any]:
    """
    Compute the composite RAG score from individual dimension scores.
    
    Applies:
    - Weighted average
    - Override rules (single Red blocks Green, 2+ Red forces Red)
    - At Risk High penalty
    """
    scored_dims = [d for d in dimensions if d.get("score") is not None]
    unknown_dims = [d for d in dimensions if d.get("score") is None]
    
    if not scored_dims:
        return {
            "overall_rag": "Unknown",
            "composite_score": 0,
            "confidence": "Low",
            "reasoning": "Insufficient data to compute a RAG score — no dimensions could be assessed.",
        }
    
    # Redistribute weights from unknown dimensions
    total_known_weight = sum(d["weight"] for d in scored_dims)
    
    weighted_sum = 0
    for d in scored_dims:
        adjusted_weight = d["weight"] / total_known_weight if total_known_weight > 0 else 0
        weighted_sum += d["score"] * adjusted_weight
    
    # Apply At Risk High penalty
    at_risk = summary.get("at_risk", "").lower()
    penalty = 0
    if at_risk in ("high", "yes", "1", "true"):
        penalty = config.AT_RISK_HIGH_PENALTY
        weighted_sum -= penalty
    
    composite_score = max(1.0, min(3.0, weighted_sum))
    
    # Determine base RAG from composite
    if composite_score >= config.COMPOSITE_GREEN_MIN:
        overall_rag = "Green"
    elif composite_score >= config.COMPOSITE_AMBER_MIN:
        overall_rag = "Amber"
    else:
        overall_rag = "Red"
    
    # Override rules
    red_dims = [d for d in scored_dims if d["score"] == RED]
    red_count = len(red_dims)
    
    overrides_applied = []
    
    if red_count >= 2:
        if overall_rag != "Red":
            overrides_applied.append(
                f"Overridden to Red: {red_count} dimensions are at Red "
                f"({', '.join(d['dimension'] for d in red_dims)})"
            )
        overall_rag = "Red"
    elif red_count == 1 and overall_rag == "Green":
        overall_rag = "Amber"
        overrides_applied.append(
            f"Capped at Amber: {red_dims[0]['dimension']} is at Red"
        )
    
    # Confidence assessment
    if len(unknown_dims) == 0:
        confidence = "High"
    elif len(unknown_dims) <= 1:
        confidence = "Medium"
    else:
        confidence = "Low"
    
    return {
        "overall_rag": overall_rag,
        "composite_score": round(composite_score, 2),
        "composite_score_raw": round(weighted_sum + penalty, 2),
        "penalty_applied": penalty,
        "red_dimension_count": red_count,
        "unknown_dimension_count": len(unknown_dims),
        "overrides_applied": overrides_applied,
        "confidence": confidence,
        "scored_dimensions": len(scored_dims),
        "total_dimensions": len(dimensions),
    }


def assess_project(project: Dict) -> Dict[str, Any]:
    """
    Run the full RAG assessment on a project.
    
    Returns a comprehensive assessment dict with dimension scores,
    composite RAG, and all supporting metrics.
    """
    tasks = project.get("plan", {}).get("tasks", [])
    summary = project.get("summary", {})
    comments = project.get("comments", [])
    
    # Score each dimension
    dim_schedule = score_schedule_adherence(tasks, summary)
    dim_completion = score_completion_progress(tasks, summary)
    dim_milestone = score_milestone_health(tasks, summary)
    dim_risk = score_task_risk_profile(tasks, summary)
    dim_stakeholder = score_stakeholder_signals(tasks, summary, comments)
    
    dimensions = [dim_schedule, dim_completion, dim_milestone, dim_risk, dim_stakeholder]
    
    # Compute composite
    composite = compute_composite_rag(dimensions, summary)
    
    # Build key risks list
    key_risks = []
    for d in dimensions:
        if d.get("score") == RED:
            key_risks.append(f"🔴 {d['dimension']}: {d['reasoning']}")
        elif d.get("score") == AMBER:
            key_risks.append(f"🟡 {d['dimension']}: {d['reasoning']}")
    
    # Build recommendations
    recommendations = []
    if dim_schedule.get("score") == RED:
        recommendations.append("Conduct an urgent schedule recovery workshop with the PM to identify acceleration opportunities.")
    if dim_completion.get("score") in (RED, AMBER):
        recommendations.append("Review resource allocation — consider adding capacity to critical path tasks.")
    if dim_milestone.get("score") == RED:
        recommendations.append("Escalate milestone delays to the steering committee with a revised timeline.")
    if dim_risk.get("score") in (RED, AMBER):
        recommendations.append("Perform a task-level triage to re-prioritize and resolve blocked items.")
    if dim_stakeholder.get("score") in (RED, AMBER):
        recommendations.append("Schedule a stakeholder alignment meeting to address concerns and reset expectations.")
    if not recommendations:
        recommendations.append("Continue current trajectory. Maintain weekly health check cadence.")
    
    return {
        "project_name": project.get("project_name", "Unknown"),
        "filename": project.get("filename", ""),
        "assessment_date": (summary.get("todays_date") or datetime.now()).strftime(config.REPORT_DATE_FORMAT),
        "overall_rag": composite["overall_rag"],
        "composite_score": composite["composite_score"],
        "confidence": composite["confidence"],
        "dimensions": dimensions,
        "composite_details": composite,
        "key_risks": key_risks,
        "recommendations": recommendations,
        "summary_snapshot": {
            "project_manager": summary.get("project_manager", "Unknown"),
            "project_stage": summary.get("project_stage", "Unknown"),
            "percent_complete": summary.get("percent_complete"),
            "project_start": summary.get("project_start").strftime(config.REPORT_DATE_FORMAT) if summary.get("project_start") else "N/A",
            "project_end": summary.get("project_end").strftime(config.REPORT_DATE_FORMAT) if summary.get("project_end") else "N/A",
            "at_risk": summary.get("at_risk", "Unknown"),
        },
        "data_quality_score": project.get("data_quality_score", 0),
    }


if __name__ == "__main__":
    # Quick test with data loader
    from data_loader import load_all_projects
    
    projects = load_all_projects()
    for p in projects:
        if "_error" in p and "plan" not in p:
            continue
        assessment = assess_project(p)
        print(f"\n{'='*60}")
        emoji = config.RAG_EMOJIS.get(assessment["overall_rag"], "⚪")
        print(f"{emoji} {assessment['project_name']}")
        print(f"  Overall: {assessment['overall_rag']} (score: {assessment['composite_score']}, confidence: {assessment['confidence']})")
        for d in assessment["dimensions"]:
            d_emoji = config.RAG_EMOJIS.get(d["label"], "⚪")
            print(f"  {d_emoji} {d['dimension']}: {d['label']} — {d['reasoning']}")
        print(f"\n  Key Risks:")
        for r in assessment["key_risks"]:
            print(f"    {r}")
        print(f"\n  Recommendations:")
        for r in assessment["recommendations"]:
            print(f"    • {r}")
