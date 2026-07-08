#  Project Health Reporting Agent

An automated AI-powered system that reads project plans (Excel), determines RAG (Red/Amber/Green) health status, provides plain-English reasoning, and generates executive-ready monthly presentations.

---

##  What It Does

1. **Reads** Excel project plans (Smartsheet/MS Project exports)
2. **Scores** project health across 5 dimensions using a weighted RAG framework
3. **Generates** weekly Markdown reports with plain-English reasoning
4. **Synthesizes** cross-project trends for monthly executive reviews
5. **Produces** a 5–7 slide PowerPoint presentation for VP-level audiences
6. **Handles** messy, incomplete data gracefully with confidence ratings

---

##  Architecture

```
Excel Files (data/)
    ↓
data_loader.py        →  Normalize & parse messy data
    ↓
rag_engine.py         →  5-dimension weighted RAG scoring
    ↓
reasoning_agent.py    →  LLM or rule-based plain-English reasoning
    ↓
report_generator.py   →  Weekly Markdown + JSON reports
    ↓
monthly_synthesis.py  →  Cross-project trend analysis
    ↓
presentation_builder.py → Executive PowerPoint (python-pptx)
```

---

## Quick Start

### 1. Create a Virtual Environment

It is highly recommended to use a virtual environment to isolate project dependencies.

```powershell
cd C:\Users\91938\Desktop\project-health-agent
py -m venv venv
.\venv\Scripts\activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Verify Setup

```powershell
py main.py --test
```

### 4. Generate Weekly Reports

```powershell
py main.py --weekly
```

### 5. Generate Monthly Presentation

```powershell
py main.py --monthly
```

### 6. Run Everything (Weekly + Monthly)

```powershell
py main.py --full
```

---

##  Project Structure

```
project-health-agent/
├── data/                          ← Input Excel files
│   ├── Project Plan B.xlsx
│   └── S2P Project.xlsx
├── outputs/
│   ├── weekly_reports/            ← Weekly health reports (Markdown + JSON)
│   └── monthly_presentation/      ← Monthly PowerPoint + synthesis
├── docs/
│   └── rag_methodology.md        ← RAG framework documentation
├── config.py                      ← All configurable thresholds
├── data_loader.py                 ← Excel parser (handles messy data)
├── rag_engine.py                  ← 5-dimension RAG scoring engine
├── reasoning_agent.py             ← LLM reasoning (Groq/Gemini) + rule-based fallback
├── report_generator.py            ← Weekly report generator
├── monthly_synthesis.py           ← Cross-project synthesis
├── presentation_builder.py        ← PowerPoint slide builder
├── main.py                        ← CLI entry point
├── requirements.txt               ← Python dependencies
├── .env.example                   ← API key template
└── README.md                      ← This file
```

---

##  Design Decisions

### Why 5 Dimensions?

Project health is multi-faceted. A single metric (like % complete) can be misleading. Our framework captures:

| Dimension | Why It Matters |
|-----------|---------------|
| **Schedule Adherence** (30%) | Are we delivering when we said we would? |
| **Completion Progress** (25%) | Is the burn rate matching the timeline? |
| **Milestone Health** (20%) | Are the big checkpoints on track? |
| **Task Risk Profile** (15%) | How many tasks are flagged as concerning? |
| **Stakeholder Signals** (10%) | What are people saying about the project? |

### Why Weighted Scoring with Overrides?

A weighted average alone can mask problems — a project could score "Green" overall while having a critical schedule failure. Our override rules prevent this:
- **Any single Red dimension** → overall capped at Amber
- **Two or more Red dimensions** → overall forced to Red

### Handling Messy Data

Real project exports are messy. The agent handles:
- Missing columns → dimension scored as "Unknown", weight redistributed
- `#UNPARSEABLE` values → gracefully skipped
- Inconsistent date formats → multi-format parser
- Missing baseline dates → schedule adherence falls back to task-level analysis
- Each report includes a **Data Quality Score** and **Confidence Level**

### LLM vs Rule-Based Reasoning

The agent works in two modes:
- **With Groq or Gemini API** → Richer, more contextual narratives (Groq is preferred, Gemini is fallback)
- **Without API key** → High-quality rule-based templates (still production-ready)

Both modes produce structured output in the same format.

---

##  Configuration

All thresholds are configurable in `config.py`:

```python
# Example: Make schedule scoring more forgiving
SCHEDULE_VARIANCE_GREEN_MAX_DAYS = 5    # Default: 3
SCHEDULE_VARIANCE_AMBER_MAX_DAYS = 15   # Default: 10
```

### Optional: LLM API Keys (Groq/Gemini)

For AI-powered reasoning, create a `.env` file and provide either a Groq or Gemini API key (Groq is used as the primary LLM, Gemini as fallback):

```
GROQ_API_KEY=your-groq-key-here
# or
GEMINI_API_KEY=your-gemini-key-here
```

Get a free key from:
- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey

---

##  Scheduled Runs (Bonus)

Run the agent on a weekly schedule:

```powershell
py main.py --schedule
```

This will:
1. Run an initial report immediately
2. Schedule subsequent runs every Monday at 9:00 AM
3. Keep running until you press Ctrl+C

For production use, you can also set up Windows Task Scheduler:

```powershell
schtasks /create /tn "ProjectHealthAgent" /tr "py C:\path\to\main.py --full" /sc weekly /d MON /st 09:00
```

---

##  Output Examples

### Weekly Report
Each project gets a Markdown report with:
- Overall RAG status with composite score
- Dimension breakdown table
- Detailed reasoning (2-4 paragraphs)
- Key metrics per dimension
- Risks and recommendations

### Monthly Presentation (7 slides)
1. **Title** — Month, portfolio snapshot (G/A/R counts)
2. **Portfolio Overview** — Table of all projects with scores
3. **Trend Analysis** — Dimension health across projects
4. **Risk Spotlight** — Top emerging risks
5. **Deep Dive** — Projects needing attention (1-2 slides)
6. **Recommendations** — Actionable next steps

---

##  License

Internal use — Professional Services team.
