# RAG Methodology — Project Health Reporting Framework

## Purpose

This document defines how the automated Project Health Reporting Agent determines the **Red / Amber / Green (RAG)** status for each project. The framework translates raw project plan data into a single, defensible health indicator with transparent reasoning.

---

## Data Sources & Assumptions

Our input data comes from structured Excel project plans (e.g., Smartsheet exports) containing:

- **Summary sheet**: Project metadata (PM, dates, overall % complete, schedule health, project stage)
- **Project Plan sheet**: Task-level data (task name, status, start/end dates, baseline dates, schedule health, variance, % complete, phase/milestone, assigned resources)
- **Comments sheet**: Stakeholder comments and observations

**Key Assumptions:**
1. "Today's Date" in the Summary sheet is the reporting snapshot date.
2. Baseline dates, when present, represent the original approved schedule.
3. `Schedule Health` (Green/Yellow/Red) is a pre-computed field from the source tool — we use it as one input signal, not as the sole determinant.
4. Budget data is **not available** in these exports — budget health is excluded from scoring (flagged as a data gap).
5. Tasks marked "Not Applicable" or "On Hold" are excluded from completion calculations.

---

## RAG Dimensions & Scoring

Each project is assessed across **five dimensions**. Each dimension produces a score: **Green (3)**, **Amber (2)**, or **Red (1)**.

| # | Dimension | Weight | What It Measures |
|---|-----------|--------|-----------------|
| 1 | **Schedule Adherence** | 30% | Are tasks completing on time relative to the baseline? |
| 2 | **Completion Progress** | 25% | Is the project on track in terms of % complete vs. elapsed time? |
| 3 | **Milestone Health** | 20% | Are key milestones (Phase/Milestone markers) on schedule? |
| 4 | **Task Risk Profile** | 15% | What proportion of tasks are flagged as at-risk, delayed, or overdue? |
| 5 | **Stakeholder Signals** | 10% | What do PM comments and source-tool health indicators suggest? |

### Dimension 1: Schedule Adherence (30%)

Measures variance between planned and actual/baseline dates.

| Status | Criteria |
|--------|----------|
| 🟢 Green | Average variance ≤ 3 days late **AND** < 10% of tasks have negative variance |
| 🟡 Amber | Average variance 4–10 days late **OR** 10–25% of tasks have negative variance |
| 🔴 Red | Average variance > 10 days late **OR** > 25% of tasks have negative variance |

*Data used:* `Baseline Start`, `Baseline Finish`, `Start Date`, `End Date`, `Variance` columns.

### Dimension 2: Completion Progress (25%)

Compares actual % complete against expected progress based on elapsed time.

| Status | Criteria |
|--------|----------|
| 🟢 Green | Actual % complete ≥ 95% of expected (time-based) |
| 🟡 Amber | Actual % complete is 80–95% of expected |
| 🔴 Red | Actual % complete < 80% of expected |

*Calculation:* `Expected % = (Today - Start) / (End - Start)`. Compare with Summary's `% Complete`.

### Dimension 3: Milestone Health (20%)

Evaluates the status of tasks at milestone/phase level (Level 0–1 tasks or those with `Phase/Milestone` values).

| Status | Criteria |
|--------|----------|
| 🟢 Green | ≥ 90% of due milestones are Complete **AND** none are Red |
| 🟡 Amber | 70–90% of due milestones are on track **OR** any milestone is Yellow |
| 🔴 Red | < 70% of due milestones are on track **OR** any milestone is Red |

*Data used:* `Phase/Milestone`, `Level`, `Status`, `Schedule Health` for milestone-level rows.

### Dimension 4: Task Risk Profile (15%)

Analyzes the distribution of task health across the project plan.

| Status | Criteria |
|--------|----------|
| 🟢 Green | ≥ 80% of active tasks are Green, < 5% are Red |
| 🟡 Amber | 60–80% of active tasks are Green **OR** 5–15% are Red |
| 🔴 Red | < 60% of active tasks are Green **OR** > 15% are Red |

*Data used:* `Schedule Health` and `RAG` columns for all non-completed, non-N/A tasks.

### Dimension 5: Stakeholder Signals (10%)

Qualitative assessment derived from PM comments, on-hold items, and source-system indicators.

| Status | Criteria |
|--------|----------|
| 🟢 Green | No concerning comments; 0 tasks on hold; summary health is Green |
| 🟡 Amber | Mixed signals; 1–3 tasks on hold; or summary health is Yellow |
| 🔴 Red | Escalation language in comments; > 3 tasks on hold; or summary health is Red |

*Data used:* `Comments` sheet, `On Hold?`, `At Risk?`, Summary `Schedule Health` and `At Risk`.

---

## Composite RAG Calculation

```
Composite Score = Σ (Dimension Score × Weight)

Where: Green = 3, Amber = 2, Red = 1
```

| Composite Score | Overall RAG |
|----------------|-------------|
| **2.5 – 3.0** | 🟢 **Green** — Project is healthy and on track |
| **1.8 – 2.49** | 🟡 **Amber** — Project has risks that need attention |
| **1.0 – 1.79** | 🔴 **Red** — Project is at serious risk, intervention required |

### Override Rules

Even if the composite score suggests Green:
- **Any single dimension at Red** → Overall cannot be Green (capped at Amber)
- **Two or more dimensions at Red** → Overall is Red regardless of composite
- **Summary-level "At Risk" = High** → Adds a 0.3 penalty to composite score

---

## Handling Missing Data

| Scenario | Approach |
|----------|----------|
| No baseline dates | Schedule Adherence scored as "Unknown" — weight redistributed to other dimensions |
| No comments | Stakeholder Signals defaults to Green (no negative signal) |
| No RAG/Schedule Health column | Task Risk Profile uses Status + date analysis as proxy |
| Budget data absent | Explicitly noted as a gap in the report; no score assigned |
| < 50% of tasks have key fields | Data quality warning added; confidence level downgraded |

---

## Output Format

Each weekly report includes:
1. **Overall RAG status** with composite score
2. **Dimension breakdown** (individual RAG per dimension with scores)
3. **Plain-English reasoning** (2–4 paragraphs explaining the status)
4. **Data quality assessment** (completeness and confidence level)
5. **Key risks and recommendations**

---

*Framework Version 1.0 | Designed for Zycus S2P Implementation Project Plans*
