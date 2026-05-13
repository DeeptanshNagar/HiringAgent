"""
Step 6: Report Generation Module.
Generates three report formats: JSON, HTML (Jinja2), and PDF (ReportLab).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.schemas import CandidateScore, ShortlistReport
from security.pii_masker import mask_dict

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _get_timestamp() -> str:
    """Get current ISO timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _get_model_info() -> Dict[str, str]:
    """Get information about the LLM model and framework used."""
    from agent.llm_factory import get_model_info
    return get_model_info()


def generate_json_report(
    job_title: str,
    candidates: List[CandidateScore],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate JSON format report.
    
    Args:
        job_title: Job title from JD.
        candidates: Ranked list of scored candidates.
        output_path: Optional specific output file path.
        
    Returns:
        Path to generated JSON file.
    """
    timestamp = _get_timestamp()
    model_info = _get_model_info()
    
    report = ShortlistReport(
        generated_at=timestamp,
        job_title=job_title,
        model_used=f"{model_info['provider']} {model_info['model']}",
        framework_used=model_info["framework"],
        total_candidates_evaluated=len(candidates),
        shortlist=candidates,
    )
    
    if output_path is None:
        safe_ts = timestamp.replace(":", "-").replace("+", "_")
        output_path = os.path.join(OUTPUT_DIR, f"shortlist_report_{safe_ts}.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)
    
    logger.info(f"JSON report generated: {output_path}")
    return output_path


def generate_html_report(
    job_title: str,
    candidates: List[CandidateScore],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate HTML format report using Jinja2 template.
    Self-contained single HTML file with inline CSS.
    
    Args:
        job_title: Job title from JD.
        candidates: Ranked list of scored candidates.
        output_path: Optional specific output file path.
        
    Returns:
        Path to generated HTML file.
    """
    from jinja2 import Template
    
    timestamp = _get_timestamp()
    model_info = _get_model_info()
    
    # Count by recommendation
    counts = {"Strong Hire": 0, "Hire": 0, "Maybe": 0, "No Hire": 0}
    for c in candidates:
        counts[c.hire_recommendation.value] = counts.get(c.hire_recommendation.value, 0) + 1
    
    # Define color scheme
    def get_badge_color(rec: str) -> str:
        colors = {
            "Strong Hire": "#28a745",
            "Hire": "#007bff",
            "Maybe": "#ffc107",
            "No Hire": "#dc3545",
        }
        return colors.get(rec, "#6c757d")
    
    def get_score_bar_color(score: float) -> str:
        if score >= 8:
            return "#28a745"
        elif score >= 6:
            return "#5cb85c"
        elif score >= 4:
            return "#ffc107"
        else:
            return "#dc3545"
    
    # Build HTML inline
    html_template = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HR Shortlist Report - {{ job_title }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #f5f6fa;
            color: #2c3e50;
            line-height: 1.6;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
        }
        header h1 { font-size: 28px; margin-bottom: 8px; }
        header p { opacity: 0.9; font-size: 14px; }
        .meta { margin-top: 15px; font-size: 12px; opacity: 0.8; }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        }
        .summary-card .count { font-size: 32px; font-weight: bold; }
        .summary-card .label { font-size: 12px; color: #7f8c8d; margin-top: 5px; }
        .candidate-card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }
        .candidate-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .candidate-name {
            font-size: 22px;
            font-weight: bold;
            color: #2c3e50;
        }
        .rank-badge {
            background: #3498db;
            color: white;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 14px;
        }
        .rec-badge {
            padding: 6px 16px;
            border-radius: 20px;
            color: white;
            font-size: 13px;
            font-weight: 600;
        }
        .score-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .score-item {
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .score-label {
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .score-bar-bg {
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        .score-bar {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        .score-value {
            font-size: 18px;
            font-weight: bold;
        }
        .justification {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
            font-style: italic;
        }
        .total-score {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin: 20px 0;
        }
        .total-score .value { font-size: 42px; font-weight: bold; }
        .total-score .label { font-size: 14px; opacity: 0.9; }
        .summary-text {
            padding: 15px;
            background: #e8f4fd;
            border-left: 4px solid #3498db;
            border-radius: 0 8px 8px 0;
            margin: 15px 0;
            font-size: 14px;
        }
        .override-note {
            padding: 12px;
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 13px;
        }
        .low-confidence {
            display: inline-block;
            padding: 4px 10px;
            background: #f8d7da;
            color: #721c24;
            border-radius: 12px;
            font-size: 11px;
            margin-top: 10px;
        }
        .escalated {
            display: inline-block;
            padding: 4px 10px;
            background: #d4edda;
            color: #155724;
            border-radius: 12px;
            font-size: 11px;
            margin-top: 10px;
        }
        footer {
            text-align: center;
            padding: 30px;
            color: #7f8c8d;
            font-size: 12px;
        }
        footer .disclaimer {
            background: #fff3cd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        @media print {
            body { background: white; padding: 0; }
            .candidate-card { break-inside: avoid; box-shadow: none; border: 1px solid #ddd; }
            header { border-radius: 0; }
        }
        @media (max-width: 768px) {
            .candidate-header { flex-direction: column; align-items: flex-start; }
            .score-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Shortlist Report</h1>
            <p>{{ job_title }}</p>
            <div class="meta">
                Generated: {{ timestamp }} | 
                Model: {{ model_used }} | 
                Framework: {{ framework }} | 
                Candidates Evaluated: {{ total_candidates }}
            </div>
        </header>

        <div class="summary-cards">
            <div class="summary-card">
                <div class="count" style="color: #28a745;">{{ counts['Strong Hire'] }}</div>
                <div class="label">Strong Hire</div>
            </div>
            <div class="summary-card">
                <div class="count" style="color: #007bff;">{{ counts['Hire'] }}</div>
                <div class="label">Hire</div>
            </div>
            <div class="summary-card">
                <div class="count" style="color: #ffc107;">{{ counts['Maybe'] }}</div>
                <div class="label">Maybe</div>
            </div>
            <div class="summary-card">
                <div class="count" style="color: #dc3545;">{{ counts['No Hire'] }}</div>
                <div class="label">No Hire</div>
            </div>
            <div class="summary-card">
                <div class="count">{{ total_candidates }}</div>
                <div class="label">Total Evaluated</div>
            </div>
        </div>

        {% for candidate in candidates %}
        <div class="candidate-card">
            <div class="candidate-header">
                <div style="display: flex; align-items: center; gap: 15px;">
                    <div class="rank-badge">#{{ candidate.rank }}</div>
                    <div class="candidate-name">{{ candidate.candidate_name }}</div>
                </div>
                <div class="rec-badge" style="background: {{ get_badge_color(candidate.hire_recommendation.value) }};">
                    {{ candidate.hire_recommendation.value }}
                </div>
            </div>

            <div class="score-grid">
                <div class="score-item">
                    <div class="score-label">Skills Match (30%)</div>
                    <div class="score-bar-bg">
                        <div class="score-bar" style="width: {{ candidate.skills.score * 10 }}%; background: {{ get_score_bar_color(candidate.skills.score) }};"></div>
                    </div>
                    <div class="score-value">{{ "%.1f"|format(candidate.skills.score) }}/10</div>
                    <div class="justification">{{ candidate.skills.justification }}</div>
                </div>
                <div class="score-item">
                    <div class="score-label">Experience (25%)</div>
                    <div class="score-bar-bg">
                        <div class="score-bar" style="width: {{ candidate.experience.score * 10 }}%; background: {{ get_score_bar_color(candidate.experience.score) }};"></div>
                    </div>
                    <div class="score-value">{{ "%.1f"|format(candidate.experience.score) }}/10</div>
                    <div class="justification">{{ candidate.experience.justification }}</div>
                </div>
                <div class="score-item">
                    <div class="score-label">Education & Certs (15%)</div>
                    <div class="score-bar-bg">
                        <div class="score-bar" style="width: {{ candidate.education.score * 10 }}%; background: {{ get_score_bar_color(candidate.education.score) }};"></div>
                    </div>
                    <div class="score-value">{{ "%.1f"|format(candidate.education.score) }}/10</div>
                    <div class="justification">{{ candidate.education.justification }}</div>
                </div>
                <div class="score-item">
                    <div class="score-label">Portfolio (20%)</div>
                    <div class="score-bar-bg">
                        <div class="score-bar" style="width: {{ candidate.portfolio.score * 10 }}%; background: {{ get_score_bar_color(candidate.portfolio.score) }};"></div>
                    </div>
                    <div class="score-value">{{ "%.1f"|format(candidate.portfolio.score) }}/10</div>
                    <div class="justification">{{ candidate.portfolio.justification }}</div>
                </div>
                <div class="score-item">
                    <div class="score-label">Communication (10%)</div>
                    <div class="score-bar-bg">
                        <div class="score-bar" style="width: {{ candidate.communication.score * 10 }}%; background: {{ get_score_bar_color(candidate.communication.score) }};"></div>
                    </div>
                    <div class="score-value">{{ "%.1f"|format(candidate.communication.score) }}/10</div>
                    <div class="justification">{{ candidate.communication.justification }}</div>
                </div>
            </div>

            <div class="total-score">
                <div class="value">{{ "%.2f"|format(candidate.weighted_total) }}</div>
                <div class="label">Weighted Total Score (out of 10.00)</div>
            </div>

            <div class="summary-text">
                <strong>Summary:</strong> {{ candidate.overall_summary }}
            </div>

            {% if candidate.low_confidence %}
            <div class="low-confidence">&#9888; Low Confidence — Manual Review Recommended</div>
            {% endif %}
            {% if candidate.escalate_for_interview %}
            <div class="escalated">&#9733; Escalated for Interview</div>
            {% endif %}
            {% if candidate.override_applied %}
            <div class="override-note">
                <strong>Override Applied:</strong> {{ candidate.override_reason }}
            </div>
            {% endif %}
        </div>
        {% endfor %}

        <footer>
            <div class="disclaimer">
                <strong>AI-Assisted Shortlisting</strong> — Final hiring decisions rest with HR.
                This report was generated by an AI agent and should be used as a screening aid only.
                All scores are explainable and subject to human override.
            </div>
            <p>Generated on {{ timestamp }} using {{ model_used }} via {{ framework }}</p>
        </footer>
    </div>
</body>
</html>
""")
    
    rendered = html_template.render(
        job_title=job_title,
        timestamp=timestamp,
        model_used=model_info["model"],
        framework=model_info["framework"],
        total_candidates=len(candidates),
        counts=counts,
        candidates=candidates,
        get_badge_color=get_badge_color,
        get_score_bar_color=get_score_bar_color,
    )
    
    if output_path is None:
        safe_ts = timestamp.replace(":", "-").replace("+", "_")
        output_path = os.path.join(OUTPUT_DIR, f"shortlist_report_{safe_ts}.html")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    
    logger.info(f"HTML report generated: {output_path}")
    return output_path


def generate_pdf_report(
    job_title: str,
    candidates: List[CandidateScore],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate PDF format report using ReportLab.
    
    Args:
        job_title: Job title from JD.
        candidates: Ranked list of scored candidates.
        output_path: Optional specific output file path.
        
    Returns:
        Path to generated PDF file.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )
    
    timestamp = _get_timestamp()
    model_info = _get_model_info()
    
    if output_path is None:
        safe_ts = timestamp.replace(":", "-").replace("+", "_")
        output_path = os.path.join(OUTPUT_DIR, f"shortlist_report_{safe_ts}.pdf")
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=20,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#7f8c8d"),
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=12,
        spaceBefore=12,
    )
    candidate_name_style = ParagraphStyle(
        "CandidateName",
        parent=styles["Heading2"],
        fontSize=18,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=6,
    )
    normal_style = styles["Normal"]
    normal_style.fontSize = 10
    normal_style.leading = 14
    
    # Color for recommendations
    def get_rec_color(rec: str) -> colors.Color:
        color_map = {
            "Strong Hire": colors.HexColor("#28a745"),
            "Hire": colors.HexColor("#007bff"),
            "Maybe": colors.HexColor("#ffc107"),
            "No Hire": colors.HexColor("#dc3545"),
        }
        return color_map.get(rec, colors.grey)
    
    story = []
    
    # --- PAGE 1: COVER ---
    story.append(Spacer(1, 4 * cm))
    
    # Logo placeholder
    logo_data = [[""]]
    logo_table = Table(logo_data, colWidths=[4 * cm], rowHeights=[3 * cm])
    logo_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 1, colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
    ]))
    story.append(logo_table)
    story.append(Spacer(1, 1 * cm))
    
    story.append(Paragraph("CONFIDENTIAL", ParagraphStyle(
        "Confidential",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#dc3545"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )))
    
    story.append(Paragraph("HR Shortlist Report", title_style))
    story.append(Paragraph(f"<b>{job_title}</b>", subtitle_style))
    story.append(Spacer(1, 0.5 * cm))
    
    # Company placeholder
    story.append(Paragraph("<b>[Company Name]</b>", ParagraphStyle(
        "Company",
        parent=styles["Normal"],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=20,
    )))
    
    story.append(Paragraph(f"Generated: {timestamp}", subtitle_style))
    story.append(Paragraph(f"Model: {model_info['provider']} {model_info['model']}", subtitle_style))
    story.append(Paragraph(f"Candidates Evaluated: {len(candidates)}", subtitle_style))
    
    story.append(Spacer(1, 2 * cm))
    
    # Confidential watermark text
    story.append(Paragraph(
        "<i>Confidential — Internal Use Only</i>",
        ParagraphStyle(
            "Watermark",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#999"),
            alignment=TA_CENTER,
        )
    ))
    
    story.append(PageBreak())
    
    # --- CANDIDATE PAGES ---
    for candidate in candidates:
        # Candidate header
        rec_color = get_rec_color(candidate.hire_recommendation.value)
        
        header_data = [
            [
                Paragraph(f"#{candidate.rank} {candidate.candidate_name}", candidate_name_style),
                Paragraph(
                    f"<b>{candidate.hire_recommendation.value}</b>",
                    ParagraphStyle(
                        "RecBadge",
                        parent=styles["Normal"],
                        fontSize=14,
                        textColor=rec_color,
                        alignment=TA_CENTER,
                    )
                ),
            ]
        ]
        header_table = Table(header_data, colWidths=[12 * cm, 4 * cm])
        header_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (1, 0), (1, 0), 2, rec_color),
            ("ROUNDEDCORNERS", [8]),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.5 * cm))
        
        # Scoring table
        table_data = [
            ["Dimension", "Weight", "Raw Score", "Weighted Score", "Justification"],
            [
                "Skills Match",
                "30%",
                f"{candidate.skills.score:.1f}/10",
                f"{candidate.skills.score * 0.30:.2f}",
                candidate.skills.justification,
            ],
            [
                "Experience Relevance",
                "25%",
                f"{candidate.experience.score:.1f}/10",
                f"{candidate.experience.score * 0.25:.2f}",
                candidate.experience.justification,
            ],
            [
                "Education & Certs",
                "15%",
                f"{candidate.education.score:.1f}/10",
                f"{candidate.education.score * 0.15:.2f}",
                candidate.education.justification,
            ],
            [
                "Project / Portfolio",
                "20%",
                f"{candidate.portfolio.score:.1f}/10",
                f"{candidate.portfolio.score * 0.20:.2f}",
                candidate.portfolio.justification,
            ],
            [
                "Communication Quality",
                "10%",
                f"{candidate.communication.score:.1f}/10",
                f"{candidate.communication.score * 0.10:.2f}",
                candidate.communication.justification,
            ],
            [
                Paragraph("<b>WEIGHTED TOTAL</b>", styles["Normal"]),
                "100%",
                "",
                Paragraph(f"<b>{candidate.weighted_total:.2f}</b>", styles["Normal"]),
                "",
            ],
        ]
        
        score_table = Table(table_data, colWidths=[3.5 * cm, 1.8 * cm, 2 * cm, 2.5 * cm, 6 * cm])
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (1, 1), (3, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8f9fa")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f4fd")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (4, 1), (4, -2), 6),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 0.5 * cm))
        
        # Overall summary box
        summary_data = [[Paragraph(f"<b>Summary:</b> {candidate.overall_summary}", normal_style)]]
        summary_table = Table(summary_data, colWidths=[16 * cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f4fd")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#3498db")),
        ]))
        story.append(summary_table)
        
        # Flags
        if candidate.low_confidence:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                "&#9888; <b>Low Confidence</b> — Manual Review Recommended",
                ParagraphStyle("Flag", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#721c24"), backColor=colors.HexColor("#f8d7da"))
            ))
        
        if candidate.override_applied:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                f"&#9998; <b>Override Applied:</b> {candidate.override_reason}",
                ParagraphStyle("Override", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#856404"), backColor=colors.HexColor("#fff3cd"))
            ))
        
        if candidate.escalate_for_interview:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                "&#9733; <b>Escalated for Interview</b>",
                ParagraphStyle("Escalated", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#155724"), backColor=colors.HexColor("#d4edda"))
            ))
        
        story.append(PageBreak())
    
    # Remove last page break
    if story and isinstance(story[-1], PageBreak):
        story.pop()
    
    # Build PDF
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(
            A4[0] / 2,
            1.5 * cm,
            f"Page {page_num} | Confidential — Internal Use Only"
        )
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    
    logger.info(f"PDF report generated: {output_path}")
    return output_path


def generate_all_reports(
    job_title: str,
    candidates: List[CandidateScore],
    timestamp_str: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate all three report formats at once.
    
    Args:
        job_title: Job title from JD.
        candidates: Ranked list of scored candidates.
        timestamp_str: Optional timestamp string for filenames.
        
    Returns:
        Dict with keys 'json', 'html', 'pdf' mapping to file paths.
    """
    if timestamp_str is None:
        timestamp_str = _get_timestamp().replace(":", "-").replace("+", "_")
    
    base_path = os.path.join(OUTPUT_DIR, f"shortlist_report_{timestamp_str}")
    
    results = {
        "json": generate_json_report(job_title, candidates, f"{base_path}.json"),
        "html": generate_html_report(job_title, candidates, f"{base_path}.html"),
        "pdf": generate_pdf_report(job_title, candidates, f"{base_path}.pdf"),
    }
    
    return results
