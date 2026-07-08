"""
Data Loader Module

Reads Excel project plan files and normalizes them into a structured format
for the RAG scoring engine. Handles messy data, missing columns, and
inconsistent formats gracefully.
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import config


def _parse_duration_to_days(duration_str: Any) -> Optional[float]:
    """Parse duration strings like '170d', '18d', '0' into float days."""
    if pd.isna(duration_str):
        return None
    s = str(duration_str).strip().lower()
    if s in ('0', ''):
        return 0.0
    match = re.match(r'^(-?\d+\.?\d*)\s*d?$', s)
    if match:
        return float(match.group(1))
    return None


def _parse_variance_to_days(variance_str: Any) -> Optional[float]:
    """Parse variance strings like '-2d', '0', '1d' into float days (negative = late)."""
    if pd.isna(variance_str):
        return None
    s = str(variance_str).strip().lower()
    if s in ('0', ''):
        return 0.0
    match = re.match(r'^(-?\d+\.?\d*)\s*d?$', s)
    if match:
        return float(match.group(1))
    return None


def _safe_parse_date(val) -> Optional[datetime]:
    """Safely parse a date value from various formats."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    s = str(val).strip()
    if s.lower() in ('#unparseable', 'nan', 'nat', ''):
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float."""
    if pd.isna(val) or val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Safely convert a value to int."""
    f = _safe_float(val)
    if f is None:
        return None
    return int(f)


def _normalize_rag_value(val) -> Optional[str]:
    """Normalize RAG/Schedule Health values to Green/Amber/Red."""
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip().lower()
    mapping = {
        'green': 'Green',
        'yellow': 'Amber',  # Yellow → Amber in our framework
        'amber': 'Amber',
        'red': 'Red',
    }
    return mapping.get(s)


def _detect_project_plan_sheet(xls: pd.ExcelFile) -> Optional[str]:
    """Find the main project plan sheet (not Comments or Summary)."""
    for name in xls.sheet_names:
        lower = name.lower()
        if lower not in ('comments', 'summary'):
            return name
    return xls.sheet_names[0] if xls.sheet_names else None


def load_summary(filepath: Path) -> Dict[str, Any]:
    """
    Load the Summary sheet and parse it into a structured dict.
    
    The Summary sheet has a key-value layout:
      Column A: field names
      Column B: field values
    """
    try:
        df = pd.read_excel(filepath, sheet_name='Summary')
    except Exception:
        return {"_error": "Summary sheet not found", "_available": False}

    summary: Dict[str, Any] = {"_available": True, "_raw": {}}
    
    # Build a key-value dict from the two-column layout
    col_a = df.columns[0]
    col_b = df.columns[1] if len(df.columns) > 1 else None
    
    if col_b is None:
        return {"_available": False, "_error": "Summary sheet has only one column"}
    
    for _, row in df.iterrows():
        key = str(row[col_a]).strip() if pd.notna(row[col_a]) else None
        val = row[col_b]
        if key:
            summary["_raw"][key] = val

    raw = summary["_raw"]
    
    summary["project_manager"] = str(raw.get("Project Manager", "Unknown"))
    summary["project_start"] = _safe_parse_date(raw.get("Project Start Date"))
    summary["project_end"] = _safe_parse_date(raw.get("Project End Date"))
    summary["not_started_count"] = _safe_int(raw.get("Not Started"))
    summary["in_progress_count"] = _safe_int(raw.get("In Progress"))
    summary["completed_count"] = _safe_int(raw.get("Completed"))
    summary["on_hold_count"] = _safe_int(raw.get("On Hold"))
    summary["at_risk"] = str(raw.get("At Risk", "")).strip()
    summary["project_stage"] = str(raw.get("Project Stage", "Unknown")).strip()
    summary["percent_complete"] = _safe_float(raw.get("% Complete"))
    summary["schedule_health"] = _normalize_rag_value(raw.get("Schedule Health"))
    summary["todays_date"] = _safe_parse_date(raw.get("Today's Date"))
    summary["duration_days"] = _safe_int(raw.get("Duration"))
    summary["project_status"] = str(raw.get("Project Status", "Unknown")).strip()

    return summary


def load_project_plan(filepath: Path) -> Dict[str, Any]:
    """
    Load the main project plan sheet and normalize task-level data.
    
    Returns a dict with normalized task list and metadata.
    """
    xls = pd.ExcelFile(filepath)
    sheet_name = _detect_project_plan_sheet(xls)
    
    if sheet_name is None:
        return {"_error": "No project plan sheet found", "tasks": [], "_available": False}
    
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    
    tasks = []
    data_quality = {
        "total_rows": len(df),
        "columns_found": list(df.columns),
        "missing_columns": [],
        "parse_warnings": [],
    }
    
    # Check for expected columns
    expected_cols = ['Task Name', 'Status', 'Start Date', 'End Date', '% Complete',
                     'Schedule Health', 'Phase/Milestone', 'Duration']
    for col in expected_cols:
        if col not in df.columns:
            data_quality["missing_columns"].append(col)
    
    for idx, row in df.iterrows():
        task = {}
        
        # Core fields
        task["row_index"] = idx
        task["task_name"] = str(row.get("Task Name", "")).strip() if pd.notna(row.get("Task Name")) else "Unnamed Task"
        task["status"] = str(row.get("Status", "")).strip() if pd.notna(row.get("Status")) else "Unknown"
        task["percent_complete"] = _safe_float(row.get("% Complete"))
        task["start_date"] = _safe_parse_date(row.get("Start Date"))
        task["end_date"] = _safe_parse_date(row.get("End Date"))
        task["duration_str"] = str(row.get("Duration", "")) if pd.notna(row.get("Duration")) else None
        task["duration_days"] = _parse_duration_to_days(row.get("Duration"))
        
        # Hierarchy
        task["level"] = _safe_int(row.get("Level", row.get("Ancestors")))
        task["phase_milestone"] = str(row.get("Phase/Milestone", "")).strip() if pd.notna(row.get("Phase/Milestone")) else None
        
        # Health indicators
        task["schedule_health"] = _normalize_rag_value(row.get("Schedule Health"))
        task["rag"] = _normalize_rag_value(row.get("RAG"))
        task["at_risk"] = True if pd.notna(row.get("At Risk?")) and row.get("At Risk?") == 1 else False
        task["on_hold"] = True if pd.notna(row.get("On Hold?")) and row.get("On Hold?") == 1 else False
        task["not_applicable"] = True if pd.notna(row.get("Not Applicable?")) and row.get("Not Applicable?") == 1 else False
        
        # Baseline data
        # Handle multiple possible baseline column names
        baseline_start = row.get("Baseline Start", row.get("Baseline Start2", row.get("Baseline Start Date")))
        baseline_finish = row.get("Baseline Finish", row.get("Baseline Finish2", row.get("Baseline End Date")))
        variance = row.get("Variance", row.get("Variance2"))
        
        task["baseline_start"] = _safe_parse_date(baseline_start)
        task["baseline_finish"] = _safe_parse_date(baseline_finish)
        task["variance_days"] = _parse_variance_to_days(variance)
        
        # People
        task["project_manager"] = str(row.get("Project Manager", "")).strip() if pd.notna(row.get("Project Manager")) else None
        task["assigned_to"] = str(row.get("Assigned To", "")).strip() if pd.notna(row.get("Assigned To")) else None
        task["owner"] = str(row.get("Owner", "")).strip() if pd.notna(row.get("Owner")) else None
        
        # Float / Critical
        task["total_float"] = _safe_float(row.get("Total Float"))
        task["is_critical"] = True if pd.notna(row.get("Critical ?")) and row.get("Critical ?") == 1 else False
        
        # Comments
        task["comments"] = str(row.get("Comments", "")).strip() if pd.notna(row.get("Comments")) else None
        task["status_comment"] = str(row.get("Status Comment", "")).strip() if pd.notna(row.get("Status Comment")) else None
        
        tasks.append(task)
    
    return {
        "_available": True,
        "sheet_name": sheet_name,
        "tasks": tasks,
        "data_quality": data_quality,
    }


def load_comments(filepath: Path) -> List[Dict[str, str]]:
    """
    Load the Comments sheet. 
    
    These sheets have inconsistent column naming (headers are actually first data row).
    We normalize to: row_ref, comment_text, author, timestamp.
    """
    try:
        df = pd.read_excel(filepath, sheet_name='Comments')
    except Exception:
        return []
    
    if df.empty or len(df.columns) < 2:
        return []
    
    comments = []
    cols = list(df.columns)
    
    # The header row itself may be data (common in these exports)
    # Check if the column names look like data
    first_col_val = str(cols[0]).strip()
    if first_col_val.startswith("Row "):
        # Header is data — include it
        header_comment = {
            "row_ref": first_col_val,
            "comment_text": str(cols[1]) if len(cols) > 1 else "",
            "author": str(cols[2]) if len(cols) > 2 else "Unknown",
            "timestamp": str(cols[3]) if len(cols) > 3 else "",
        }
        comments.append(header_comment)
    
    for _, row in df.iterrows():
        vals = [row.iloc[i] if i < len(row) else None for i in range(min(4, len(cols)))]
        if all(pd.isna(v) for v in vals):
            continue
        
        comment = {
            "row_ref": str(vals[0]) if pd.notna(vals[0]) else "",
            "comment_text": str(vals[1]) if len(vals) > 1 and pd.notna(vals[1]) else "",
            "author": str(vals[2]) if len(vals) > 2 and pd.notna(vals[2]) else "Unknown",
            "timestamp": str(vals[3]) if len(vals) > 3 and pd.notna(vals[3]) else "",
        }
        if comment["comment_text"]:
            comments.append(comment)
    
    return comments


def load_project(filepath: Path) -> Dict[str, Any]:
    """
    Load a complete project from an Excel file.
    
    Returns a unified project dict with summary, tasks, comments, and metadata.
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return {"_error": f"File not found: {filepath}", "filename": filepath.name}
    
    project_name = filepath.stem  # Filename without extension
    
    summary = load_summary(filepath)
    plan_data = load_project_plan(filepath)
    comments = load_comments(filepath)
    
    # Derive project name from the first task (level 0) if available
    if plan_data.get("_available") and plan_data["tasks"]:
        for task in plan_data["tasks"]:
            if task.get("level") == 0 and task.get("task_name"):
                project_name = task["task_name"]
                break
    
    # Calculate data quality score
    total_fields = 0
    populated_fields = 0
    
    if plan_data.get("_available"):
        key_fields = ['status', 'start_date', 'end_date', 'percent_complete', 'schedule_health']
        for task in plan_data["tasks"]:
            for field in key_fields:
                total_fields += 1
                if task.get(field) is not None:
                    populated_fields += 1
    
    data_quality_score = (populated_fields / total_fields * 100) if total_fields > 0 else 0
    
    return {
        "filename": filepath.name,
        "project_name": project_name,
        "summary": summary,
        "plan": plan_data,
        "comments": comments,
        "data_quality_score": round(data_quality_score, 1),
        "loaded_at": datetime.now().isoformat(),
    }


def load_all_projects() -> List[Dict[str, Any]]:
    """
    Load all Excel files from the data directory.
    
    Returns a list of project dicts.
    """
    projects = []
    data_dir = config.DATA_DIR
    
    if not data_dir.exists():
        print(f"⚠️  Data directory not found: {data_dir}")
        return projects
    
    excel_files = sorted(data_dir.glob("*.xlsx")) + sorted(data_dir.glob("*.xls"))
    
    if not excel_files:
        print(f"⚠️  No Excel files found in: {data_dir}")
        return projects
    
    for filepath in excel_files:
        print(f"📂 Loading: {filepath.name}")
        try:
            project = load_project(filepath)
            projects.append(project)
            print(f"   ✅ Loaded — {len(project['plan'].get('tasks', []))} tasks, "
                  f"data quality: {project['data_quality_score']}%")
        except Exception as e:
            print(f"   ❌ Error loading {filepath.name}: {e}")
            projects.append({
                "filename": filepath.name,
                "project_name": filepath.stem,
                "_error": str(e),
            })
    
    return projects


if __name__ == "__main__":
    # Quick test
    projects = load_all_projects()
    for p in projects:
        print(f"\n{'='*60}")
        print(f"Project: {p['project_name']}")
        if '_error' in p and 'plan' not in p:
            print(f"  Error: {p['_error']}")
            continue
        print(f"  File: {p['filename']}")
        print(f"  Data Quality: {p['data_quality_score']}%")
        s = p.get('summary', {})
        if s.get('_available'):
            print(f"  PM: {s.get('project_manager')}")
            print(f"  Stage: {s.get('project_stage')}")
            print(f"  % Complete: {s.get('percent_complete')}")
            print(f"  Schedule Health: {s.get('schedule_health')}")
            print(f"  At Risk: {s.get('at_risk')}")
        tasks = p.get('plan', {}).get('tasks', [])
        statuses = {}
        for t in tasks:
            st = t.get('status', 'Unknown')
            statuses[st] = statuses.get(st, 0) + 1
        print(f"  Task Status Distribution: {statuses}")
        health_dist = {}
        for t in tasks:
            h = t.get('schedule_health') or t.get('rag') or 'Unknown'
            health_dist[h] = health_dist.get(h, 0) + 1
        print(f"  Health Distribution: {health_dist}")
        print(f"  Comments: {len(p.get('comments', []))}")
