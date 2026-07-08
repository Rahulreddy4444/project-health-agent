"""
Configuration module for the Project Health Reporting Agent.

Centralizes all configurable thresholds, paths, and settings.
"""

import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
WEEKLY_DIR = OUTPUT_DIR / "weekly_reports"
MONTHLY_DIR = OUTPUT_DIR / "monthly_presentation"
DOCS_DIR = BASE_DIR / "docs"

# Ensure output directories exist
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
MONTHLY_DIR.mkdir(parents=True, exist_ok=True)

# ─── LLM Configuration ──────────────────────────────────────────────────────

# Load .env if present
try:
    # pyrefly: ignore [missing-import]
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
USE_LLM = bool(GEMINI_API_KEY or GROQ_API_KEY)  # Falls back to rule-based reasoning if no key

# ─── RAG Dimension Weights ──────────────────────────────────────────────────

WEIGHTS = {
    "schedule_adherence": 0.30,
    "completion_progress": 0.25,
    "milestone_health": 0.20,
    "task_risk_profile": 0.15,
    "stakeholder_signals": 0.10,
}

# ─── Schedule Adherence Thresholds ───────────────────────────────────────────

SCHEDULE_VARIANCE_GREEN_MAX_DAYS = 3       # Average variance ≤ 3 days → Green
SCHEDULE_VARIANCE_AMBER_MAX_DAYS = 10      # Average variance ≤ 10 days → Amber
SCHEDULE_LATE_TASKS_GREEN_MAX_PCT = 0.10   # < 10% late tasks → Green
SCHEDULE_LATE_TASKS_AMBER_MAX_PCT = 0.25   # < 25% late tasks → Amber

# ─── Completion Progress Thresholds ──────────────────────────────────────────

COMPLETION_GREEN_RATIO = 0.95   # Actual/Expected ≥ 95% → Green
COMPLETION_AMBER_RATIO = 0.80   # Actual/Expected ≥ 80% → Amber

# ─── Milestone Health Thresholds ─────────────────────────────────────────────

MILESTONE_GREEN_ON_TRACK_PCT = 0.90   # ≥ 90% on track → Green
MILESTONE_AMBER_ON_TRACK_PCT = 0.70   # ≥ 70% on track → Amber

# ─── Task Risk Profile Thresholds ────────────────────────────────────────────

TASK_RISK_GREEN_HEALTHY_PCT = 0.80     # ≥ 80% Green tasks → Green
TASK_RISK_GREEN_RED_MAX_PCT = 0.05     # < 5% Red tasks (for Green)
TASK_RISK_AMBER_HEALTHY_PCT = 0.60     # ≥ 60% Green tasks → Amber
TASK_RISK_AMBER_RED_MAX_PCT = 0.15     # < 15% Red tasks (for Amber)

# ─── Stakeholder Signals Thresholds ──────────────────────────────────────────

ON_HOLD_AMBER_THRESHOLD = 1   # 1-3 on-hold tasks → Amber
ON_HOLD_RED_THRESHOLD = 4     # > 3 on-hold tasks → Red

# ─── Composite Score Thresholds ──────────────────────────────────────────────

COMPOSITE_GREEN_MIN = 2.5     # ≥ 2.5 → Green
COMPOSITE_AMBER_MIN = 1.8     # ≥ 1.8 → Amber (below → Red)

# ─── Override Rules ──────────────────────────────────────────────────────────

AT_RISK_HIGH_PENALTY = 0.3    # Penalty if Summary "At Risk" = High

# ─── RAG Color Mapping ──────────────────────────────────────────────────────

RAG_SCORES = {"Green": 3, "Amber": 2, "Red": 1, "Unknown": None}
RAG_LABELS = {3: "Green", 2: "Amber", 1: "Red"}
RAG_EMOJIS = {"Green": "🟢", "Amber": "🟡", "Red": "🔴", "Unknown": "⚪"}

# ─── Report Settings ────────────────────────────────────────────────────────

REPORT_DATE_FORMAT = "%Y-%m-%d"
WEEKLY_SCHEDULE_DAY = "monday"  # Day of week for scheduled runs
WEEKLY_SCHEDULE_TIME = "09:00"  # Time for scheduled runs
