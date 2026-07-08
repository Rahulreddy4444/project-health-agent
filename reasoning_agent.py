"""
LLM Reasoning Agent

Uses Google Gemini (or falls back to rule-based templates) to generate
plain-English reasoning behind the RAG status. Provides executive-ready
narratives rather than raw numbers.
"""

import os
import json
from typing import Dict, Any, Optional

import config


def _build_prompt(assessment: Dict[str, Any]) -> str:
    """Build a structured prompt for the LLM from the assessment data."""
    
    dims_text = ""
    for d in assessment["dimensions"]:
        emoji = config.RAG_EMOJIS.get(d["label"], "⚪")
        dims_text += f"\n  {emoji} {d['dimension']} ({d['weight']*100:.0f}% weight): {d['label']}"
        dims_text += f"\n     Reasoning: {d['reasoning']}"
        if d.get("metrics"):
            key_metrics = {k: v for k, v in d["metrics"].items() 
                         if k not in ("data_available", "comment_excerpts")}
            dims_text += f"\n     Key Metrics: {json.dumps(key_metrics, default=str)}"
    
    risks_text = "\n".join(f"  - {r}" for r in assessment.get("key_risks", [])) or "  None identified"
    recs_text = "\n".join(f"  - {r}" for r in assessment.get("recommendations", [])) or "  None"
    
    snapshot = assessment.get("summary_snapshot", {})
    
    prompt = f"""You are a Professional Services project health analyst. Based on the following RAG assessment data, write a clear, plain-English executive summary of this project's health status.

PROJECT: {assessment['project_name']}
PROJECT MANAGER: {snapshot.get('project_manager', 'N/A')}
STAGE: {snapshot.get('project_stage', 'N/A')}
TIMELINE: {snapshot.get('project_start', 'N/A')} to {snapshot.get('project_end', 'N/A')}
OVERALL COMPLETION: {snapshot.get('percent_complete', 'N/A')}
ASSESSMENT DATE: {assessment.get('assessment_date', 'N/A')}

OVERALL RAG: {assessment['overall_rag']} (composite score: {assessment['composite_score']}/3.00)
CONFIDENCE: {assessment['confidence']}
DATA QUALITY: {assessment.get('data_quality_score', 'N/A')}%

DIMENSION BREAKDOWN:{dims_text}

KEY RISKS:
{risks_text}

RECOMMENDATIONS:
{recs_text}

OVERRIDES APPLIED: {assessment.get('composite_details', {}).get('overrides_applied', 'None')}

---

Write your response in this exact format:

## Executive Summary
[2-3 sentences summarizing the project's overall health, suitable for a VP-level audience. Lead with the status and key headline.]

## Detailed Analysis
[3-4 paragraphs explaining the reasoning behind each dimension's score. Be specific — reference actual numbers and metrics. Explain what's working and what's concerning.]

## Key Risks & Watch Items
[Bullet points listing the top risks with context. Not just "schedule is behind" — explain the impact and urgency.]

## Recommended Actions
[Numbered list of specific, actionable recommendations. Each should be concrete enough for a PM to execute.]

## Data Quality Note
[1-2 sentences about the completeness and reliability of the data used for this assessment.]

Keep the language professional, direct, and jargon-free. A non-technical executive should be able to read this and understand the project's situation.
"""
    return prompt


def _generate_with_llm(prompt: str) -> Optional[str]:
    """Generate reasoning using Groq API or Google Gemini API."""
    if config.GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=config.GROQ_API_KEY)
            
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=2000,
            )
            return chat_completion.choices[0].message.content
        except ImportError:
            print("⚠️  groq package not installed. Try: py -m pip install groq")
        except Exception as e:
            print(f"⚠️  Groq API error: {e}. Falling back...")
            
    if config.GEMINI_API_KEY:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import google.generativeai as genai
            
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 2000,
                }
            )
            
            return response.text
        except ImportError:
            print("⚠️  google-generativeai package not installed. Using rule-based reasoning.")
        except Exception as e:
            print(f"⚠️  Gemini API error: {e}. Falling back to rule-based reasoning.")
            
    return None


def _generate_rule_based(assessment: Dict[str, Any]) -> str:
    """Generate reasoning using rule-based templates (no LLM needed)."""
    
    overall = assessment["overall_rag"]
    score = assessment["composite_score"]
    snapshot = assessment.get("summary_snapshot", {})
    dims = assessment["dimensions"]
    
    emoji = config.RAG_EMOJIS.get(overall, "⚪")
    
    # Executive Summary
    if overall == "Green":
        exec_summary = (
            f"The **{assessment['project_name']}** project is currently rated {emoji} **Green** "
            f"with a composite health score of {score}/3.00. The project is broadly on track "
            f"with {snapshot.get('percent_complete', 'N/A')} completion and no critical concerns requiring escalation."
        )
    elif overall == "Amber":
        concerns = [d["dimension"] for d in dims if d.get("label") in ("Amber", "Red")]
        exec_summary = (
            f"The **{assessment['project_name']}** project is rated {emoji} **Amber** "
            f"with a composite score of {score}/3.00. While progress is being made, "
            f"concerns exist in {', '.join(concerns)}. "
            f"Proactive intervention is recommended to prevent further deterioration."
        )
    else:
        red_dims = [d["dimension"] for d in dims if d.get("label") == "Red"]
        exec_summary = (
            f"The **{assessment['project_name']}** project is rated {emoji} **Red** "
            f"with a composite score of {score}/3.00. The project faces significant risks in "
            f"{', '.join(red_dims)}. Immediate executive attention and intervention is required."
        )
    
    # Detailed Analysis
    detail_parts = []
    for d in dims:
        d_emoji = config.RAG_EMOJIS.get(d.get("label", "Unknown"), "⚪")
        detail_parts.append(f"**{d_emoji} {d['dimension']}** ({d['weight']*100:.0f}% weight): {d['reasoning']}")
    
    detail_text = "\n\n".join(detail_parts)
    
    # Key Risks
    risks = assessment.get("key_risks", [])
    risks_text = "\n".join(f"- {r}" for r in risks) if risks else "- No critical risks identified at this time."
    
    # Recommendations
    recs = assessment.get("recommendations", [])
    recs_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(recs))
    
    # Data Quality
    dq = assessment.get("data_quality_score", 0)
    confidence = assessment.get("confidence", "Unknown")
    if dq >= 80:
        dq_text = f"Data quality is strong at {dq}% completeness (confidence: {confidence}). Assessment is well-supported by available data."
    elif dq >= 50:
        dq_text = f"Data quality is moderate at {dq}% completeness (confidence: {confidence}). Some dimensions may have limited data support — interpret with appropriate caution."
    else:
        dq_text = f"Data quality is limited at {dq}% completeness (confidence: {confidence}). This assessment should be supplemented with direct PM input for higher confidence."
    
    # Overrides
    overrides = assessment.get("composite_details", {}).get("overrides_applied", [])
    override_text = ""
    if overrides:
        override_text = "\n\n> **Note:** " + "; ".join(overrides)
    
    return f"""## Executive Summary

{exec_summary}

## Detailed Analysis

{detail_text}

## Key Risks & Watch Items

{risks_text}

## Recommended Actions

{recs_text}

## Data Quality Note

{dq_text}{override_text}"""


def generate_reasoning(assessment: Dict[str, Any]) -> str:
    """
    Generate plain-English reasoning for a project assessment.
    
    Uses Gemini API if configured, otherwise falls back to rule-based templates.
    Both produce structured, executive-ready output.
    """
    if config.USE_LLM:
        prompt = _build_prompt(assessment)
        llm_result = _generate_with_llm(prompt)
        if llm_result:
            return llm_result
    
    # Fallback to rule-based
    return _generate_rule_based(assessment)


def generate_cross_project_synthesis(assessments: list) -> str:
    """
    Generate a synthesis narrative across multiple projects.
    Used for monthly reporting.
    """
    if not assessments:
        return "No project assessments available for synthesis."
    
    # Aggregate stats
    rag_dist = {"Green": 0, "Amber": 0, "Red": 0}
    all_risks = []
    all_recs = []
    trending_concerns = []
    
    for a in assessments:
        rag = a.get("overall_rag", "Unknown")
        if rag in rag_dist:
            rag_dist[rag] += 1
        all_risks.extend(a.get("key_risks", []))
        all_recs.extend(a.get("recommendations", []))
        
        # Check dimension-level patterns
        for d in a.get("dimensions", []):
            if d.get("label") in ("Red", "Amber"):
                trending_concerns.append({
                    "project": a.get("project_name"),
                    "dimension": d["dimension"],
                    "status": d["label"],
                    "detail": d.get("reasoning", ""),
                })
    
    total = sum(rag_dist.values())
    
    # Find common dimension issues
    dim_issues = {}
    for tc in trending_concerns:
        dim = tc["dimension"]
        dim_issues[dim] = dim_issues.get(dim, 0) + 1
    
    # Build synthesis
    if config.USE_LLM:
        prompt = f"""You are a VP-level Professional Services analyst. Generate a cross-project synthesis for a monthly executive review.

PORTFOLIO SUMMARY:
- Total projects: {total}
- Green: {rag_dist['Green']}, Amber: {rag_dist['Amber']}, Red: {rag_dist['Red']}

COMMON DIMENSION ISSUES (dimensions appearing as Amber/Red across projects):
{json.dumps(dim_issues, indent=2)}

INDIVIDUAL PROJECT CONCERNS:
{json.dumps(trending_concerns, indent=2, default=str)}

ALL KEY RISKS:
{json.dumps(all_risks, indent=2, default=str)}

Write a 3-paragraph executive synthesis that:
1. Summarizes portfolio health and overall trend direction
2. Identifies cross-cutting themes (not just project-by-project)
3. Provides 3-5 strategic recommendations for leadership

Be concise, insightful, and actionable. Avoid repeating individual project details — focus on patterns and portfolio-level insights."""
        
        result = _generate_with_llm(prompt)
        if result:
            return result
    
    # Rule-based synthesis
    health_label = "healthy" if rag_dist["Green"] > rag_dist["Red"] else "under pressure"
    
    synthesis = f"""## Portfolio Health Summary

Across {total} active projects, the portfolio is **{health_label}**: """
    synthesis += f"{rag_dist['Green']} Green, {rag_dist['Amber']} Amber, {rag_dist['Red']} Red.\n\n"
    
    if dim_issues:
        most_common = max(dim_issues.items(), key=lambda x: x[1])
        synthesis += f"**Cross-Cutting Theme:** The most common area of concern is **{most_common[0]}**, "
        synthesis += f"flagged in {most_common[1]} project(s). "
    
    if trending_concerns:
        synthesis += "\n\n**Emerging Risks:**\n"
        for tc in trending_concerns[:5]:
            emoji = config.RAG_EMOJIS.get(tc["status"], "⚪")
            synthesis += f"- {emoji} **{tc['project']}** — {tc['dimension']}: {tc['detail']}\n"
    
    # Deduplicate recommendations
    unique_recs = list(dict.fromkeys(all_recs))
    synthesis += "\n\n**Portfolio-Level Recommendations:**\n"
    for i, r in enumerate(unique_recs[:5], 1):
        synthesis += f"{i}. {r}\n"
    
    return synthesis


if __name__ == "__main__":
    from data_loader import load_all_projects
    from rag_engine import assess_project
    
    projects = load_all_projects()
    for p in projects:
        if "_error" in p and "plan" not in p:
            continue
        assessment = assess_project(p)
        reasoning = generate_reasoning(assessment)
        print(f"\n{'='*70}")
        print(f"PROJECT: {assessment['project_name']}")
        print(f"{'='*70}")
        print(reasoning)
