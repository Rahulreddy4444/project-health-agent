"""
Project Health Reporting Agent — Main Entry Point

Usage:
    py main.py --weekly          Generate weekly health reports for all projects
    py main.py --monthly         Generate monthly synthesis + PowerPoint
    py main.py --full            Run both weekly + monthly
    py main.py --schedule        Run weekly on a schedule (every Monday 9 AM)
    py main.py --test            Quick test to verify setup
"""

import sys
import os
import argparse
from datetime import datetime

# Fix Windows console encoding for emoji/Unicode
if sys.platform == "win32":
    import io
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import config
from data_loader import load_all_projects
from report_generator import generate_all_weekly_reports
from monthly_synthesis import generate_monthly_report


def run_weekly():
    """Generate weekly health reports for all projects."""
    print("\n" + "=" * 60)
    print(" PROJECT HEALTH REPORTING AGENT — Weekly Run")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Check LLM status
    if config.GROQ_API_KEY:
        print(" LLM Mode: Groq API (enhanced reasoning)")
    elif config.GEMINI_API_KEY:
        print(" LLM Mode: Gemini API (enhanced reasoning)")
    else:
        print(" LLM Mode: Rule-based (no API key configured)")
        print("   Tip: Add GROQ_API_KEY to .env for AI-powered reasoning")
    
    # Load projects
    print(f"\n Loading project data from: {config.DATA_DIR}")
    projects = load_all_projects()
    
    if not projects:
        print(" No projects found. Place Excel files in the 'data/' directory.")
        return []
    
    # Generate reports
    print(f"\n Generating weekly health reports...")
    assessments = generate_all_weekly_reports(projects)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ WEEKLY SUMMARY")
    print(f"{'='*60}")
    
    for a in assessments:
        emoji = config.RAG_EMOJIS.get(a.get("overall_rag", "Unknown"), "⚪")
        print(f"  {emoji} {a['project_name']}: {a['overall_rag']} "
              f"(score: {a['composite_score']}, confidence: {a['confidence']})")
    
    print(f"\n📁 Reports saved to: {config.WEEKLY_DIR}")
    
    return assessments


def run_monthly(assessments=None):
    """Generate monthly synthesis and executive presentation."""
    print("\n" + "=" * 60)
    print(" PROJECT HEALTH REPORTING AGENT — Monthly Synthesis")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    pptx_path = generate_monthly_report(assessments)
    
    if pptx_path:
        print(f"\n{'='*60}")
        print(f"✅ MONTHLY DELIVERABLES")
        print(f"{'='*60}")
        print(f"  Presentation: {pptx_path}")
        print(f"  All outputs: {config.MONTHLY_DIR}")
    
    return pptx_path


def run_full():
    """Run both weekly reports and monthly synthesis."""
    assessments = run_weekly()
    if assessments:
        run_monthly(assessments)


def run_schedule():
    """Run weekly reports on a schedule."""
    try:
        import schedule
        import time
    except ImportError:
        print(" 'schedule' package not installed. Run: py -m pip install schedule")
        return
    
    day = config.WEEKLY_SCHEDULE_DAY
    time_str = config.WEEKLY_SCHEDULE_TIME
    
    print(f"\n Scheduling weekly runs every {day.title()} at {time_str}")
    print(f"   Press Ctrl+C to stop.\n")
    
    # Map day names to schedule methods
    day_map = {
        "monday": schedule.every().monday,
        "tuesday": schedule.every().tuesday,
        "wednesday": schedule.every().wednesday,
        "thursday": schedule.every().thursday,
        "friday": schedule.every().friday,
        "saturday": schedule.every().saturday,
        "sunday": schedule.every().sunday,
    }
    
    scheduler = day_map.get(day.lower(), schedule.every().monday)
    scheduler.at(time_str).do(run_weekly)
    
    # Run once immediately
    print(" Running initial report now...")
    run_weekly()
    
    print(f"\n Next scheduled run: {day.title()} at {time_str}")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n\n Scheduler stopped.")


def run_test():
    """Quick test to verify everything is set up correctly."""
    print("\n Running Setup Test...")
    print("=" * 60)
    
    # Check dependencies
    print("\n1. Checking dependencies...")
    deps = {
        "pandas": False,
        "openpyxl": False,
        "pptx": False,
    }
    
    try:
        import pandas
        deps["pandas"] = True
        print(f"   ✅ pandas {pandas.__version__}")
    except ImportError:
        print("   ❌ pandas — run: py -m pip install pandas")
    
    try:
        import openpyxl
        deps["openpyxl"] = True
        print(f"   ✅ openpyxl {openpyxl.__version__}")
    except ImportError:
        print("   ❌ openpyxl — run: py -m pip install openpyxl")
    
    try:
        from pptx import __version__ as pptx_version
        deps["pptx"] = True
        print(f"   ✅ python-pptx {pptx_version}")
    except ImportError:
        print("   ❌ python-pptx — run: py -m pip install python-pptx")
    
    # Check optional deps
    print("\n2. Checking optional dependencies...")
    try:
        import groq
        print(f"   ✅ groq (Primary LLM)")
    except ImportError:
        print("   ⚠️  groq not installed")
        
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import google.generativeai
        print(f"   ✅ google-generativeai (Fallback LLM)")
    except ImportError:
        print("   ⚠️  google-generativeai not installed")
    
    # Check API key
    print("\n3. Checking configuration...")
    if config.GROQ_API_KEY:
        print(f"   ✅ GROQ_API_KEY configured")
    elif config.GEMINI_API_KEY:
        print(f"   ✅ GEMINI_API_KEY configured")
    else:
        print(f"   ⚠️  No LLM API keys — will use rule-based reasoning (still works great!)")
    
    # Check data files
    print(f"\n4. Checking data files in {config.DATA_DIR}...")
    excel_files = list(config.DATA_DIR.glob("*.xlsx")) + list(config.DATA_DIR.glob("*.xls"))
    if excel_files:
        for f in excel_files:
            print(f"   ✅ {f.name} ({f.stat().st_size / 1024:.0f} KB)")
    else:
        print(f"   ❌ No Excel files found. Place your project plans in: {config.DATA_DIR}")
    
    # Check output directories
    print(f"\n5. Checking output directories...")
    print(f"   ✅ Weekly reports: {config.WEEKLY_DIR}")
    print(f"   ✅ Monthly output: {config.MONTHLY_DIR}")
    
    # All good?
    all_deps = all(deps.values())
    has_data = bool(excel_files)
    
    print(f"\n{'='*60}")
    if all_deps and has_data:
        print("🎉 All checks passed! Ready to run.")
        print(f"\n   Try: py main.py --full")
    elif all_deps:
        print("⚠️  Dependencies OK but no data files found.")
        print(f"   Place Excel files in: {config.DATA_DIR}")
    else:
        missing = [k for k, v in deps.items() if not v]
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print(f"   Run: py -m pip install -r requirements.txt")


def main():
    parser = argparse.ArgumentParser(
        description="Project Health Reporting Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py main.py --test              Check setup
  py main.py --weekly            Generate weekly reports
  py main.py --monthly           Generate monthly presentation
  py main.py --full              Run weekly + monthly
  py main.py --schedule          Auto-run weekly on schedule
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--weekly", action="store_true", help="Generate weekly health reports")
    group.add_argument("--monthly", action="store_true", help="Generate monthly synthesis + presentation")
    group.add_argument("--full", action="store_true", help="Run both weekly and monthly")
    group.add_argument("--schedule", action="store_true", help="Schedule weekly runs")
    group.add_argument("--test", action="store_true", help="Test setup and dependencies")
    
    args = parser.parse_args()
    
    if args.test:
        run_test()
    elif args.weekly:
        run_weekly()
    elif args.monthly:
        run_monthly()
    elif args.full:
        run_full()
    elif args.schedule:
        run_schedule()


if __name__ == "__main__":
    main()
