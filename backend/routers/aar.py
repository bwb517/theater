import json
import uuid
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_optional_user, get_current_user
from cost_guard import check_token_budget
from limiter import limiter
import models
import ai_client
import briefing
import forecasting
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend


def _esc(text) -> str:
    """XML-escape a value for safe use inside a reportlab Paragraph.

    reportlab parses '&', '<', '>' as markup, so an unescaped scenario title or
    unit name (e.g. 'A & B <Recon>') would otherwise crash PDF generation.
    """
    return _xml_escape("" if text is None else str(text))

router = APIRouter(prefix="/api/sessions", tags=["aar"])

class AARRequest(BaseModel):
    gm_notes: Optional[str] = ""
    verbosity: int = 2

@router.post("/{session_id}/aar")
@limiter.limit("10/hour")
async def generate_aar(
    request: Request,
    session_id: str,
    req: AARRequest,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
    _: models.User = Depends(check_token_budget),
):
    """Generate a complete After Action Review for a session."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()

    scenario = {
        "title": scenario_obj.title,
        "scenario_type": scenario_obj.scenario_type,
        "timeframe": scenario_obj.timeframe,
        "situation": json.loads(scenario_obj.situation or "{}"),
        "factions": json.loads(scenario_obj.factions or "[]"),
        "win_conditions": json.loads(scenario_obj.win_conditions or "{}"),
        "ai_notes": scenario_obj.ai_notes
    }

    turn_logs = [{
        "turn_number": t.turn_number,
        "player_moves": json.loads(t.player_moves or "[]"),
        "ai_moves": json.loads(t.ai_moves or "[]"),
        "adjudication": json.loads(t.adjudication or "{}"),
        "game_master_notes": t.game_master_notes
    } for t in session.turn_logs]

    final_state = json.loads(session.current_game_state or "{}")

    mc = db.query(models.MonteCarloResult).filter(
        models.MonteCarloResult.session_id == session_id
    ).order_by(models.MonteCarloResult.created_at.desc()).first()
    mc_data = json.loads(mc.results or "{}") if mc else None

    try:
        aar_content = await ai_client.generate_aar(
            scenario=scenario,
            turn_logs=turn_logs,
            final_state=final_state,
            monte_carlo=mc_data,
            gm_notes=req.gm_notes or "",
            verbosity=req.verbosity,
            user_id=user.id if user else None,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(500, f"AAR generation failed: {str(e)}")

    # Section 8: Forecasting Accuracy — only when forecasting is enabled and ≥1 forecast
    # exists. Numbers are deterministic; only the narrative paragraph uses Claude (hybrid),
    # and a templated fallback keeps the section rendering if that call fails.
    if session.forecasting_enabled:
        forecast_rows = db.query(models.TurnForecast).filter(
            models.TurnForecast.session_id == session_id
        ).all()
        if forecast_rows:
            section8 = await _build_forecasting_section(
                forecast_rows, session, user_id=user.id if user else None
            )
            aar_content["section_8_forecasting_accuracy"] = section8

    aar = models.AARReport(
        session_id=session_id,
        content=json.dumps(aar_content),
        share_token=str(uuid.uuid4())
    )
    db.add(aar)
    db.commit()
    db.refresh(aar)

    return {
        "id": aar.id,
        "share_token": aar.share_token,
        "content": aar_content,
        "created_at": aar.created_at.isoformat()
    }

@router.get("/{session_id}/aar")
def get_aar(session_id: str, db: Session = Depends(get_db)):
    aar = db.query(models.AARReport).filter(
        models.AARReport.session_id == session_id
    ).order_by(models.AARReport.created_at.desc()).first()
    if not aar:
        raise HTTPException(404, "No AAR found for this session")
    return {
        "id": aar.id,
        "share_token": aar.share_token,
        "content": json.loads(aar.content or "{}"),
        "created_at": aar.created_at.isoformat()
    }

@router.get("/{session_id}/aar/pdf")
def export_aar_pdf(session_id: str, db: Session = Depends(get_db)):
    """Export AAR as a formatted PDF document."""
    aar = db.query(models.AARReport).filter(
        models.AARReport.session_id == session_id
    ).order_by(models.AARReport.created_at.desc()).first()
    if not aar:
        raise HTTPException(404, "No AAR found")

    content = json.loads(aar.content or "{}")
    pdf_bytes = build_aar_pdf(content)

    title = content.get("metadata", {}).get("exercise_title", "AAR")
    filename = f"THEATER_AAR_{title.replace(' ', '_')[:30]}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/aar/share/{token}")
def get_shared_aar(token: str, db: Session = Depends(get_db)):
    aar = db.query(models.AARReport).filter(models.AARReport.share_token == token).first()
    if not aar:
        raise HTTPException(404, "AAR not found")
    return {
        "id": aar.id,
        "content": json.loads(aar.content or "{}"),
        "created_at": aar.created_at.isoformat()
    }

def _fallback_calibration_narrative(summary: dict) -> str:
    """Templated calibration narrative used when the Claude call is unavailable."""
    rating = summary.get("calibration_rating", "Insufficient data")
    avg = summary.get("average_brier_score")
    avg_txt = f"{avg:.3f}" if isinstance(avg, (int, float)) else "—"
    base = (
        f"Across {summary.get('forecasts_resolved', 0)} scored turn(s), your average Brier "
        f"score was {avg_txt} (0 = perfect, 2 = worst; Brier, 1950). "
    )
    tail = {
        "Well-calibrated": "Your stated probabilities tracked actual outcomes closely — keep "
                           "expressing uncertainty at the level you genuinely feel.",
        "Overconfident": "You tended to state higher probabilities than events warranted — "
                         "pull extreme estimates back toward the middle when evidence is thin.",
        "Underconfident": "You tended to hedge below what outcomes warranted — when the "
                          "evidence is strong, commit to more decisive probabilities.",
    }.get(rating, "Submit more forecasts to build a meaningful calibration picture.")
    return base + tail


async def _build_forecasting_section(forecast_rows, session, user_id=None) -> dict:
    """Deterministic Section 8 payload + a Claude (or templated) narrative paragraph."""
    summary = forecasting.build_forecasting_summary(
        forecast_rows, total_turns=session.current_turn
    )
    try:
        narrative = await ai_client.forecasting_narrative(
            summary, user_id=user_id, session_id=session.id
        )
        if not narrative:
            narrative = _fallback_calibration_narrative(summary)
    except Exception:
        narrative = _fallback_calibration_narrative(summary)
    return {
        "average_brier_score": summary.get("average_brier_score"),
        "calibration_rating": summary.get("calibration_rating"),
        "forecasts_submitted": summary.get("forecasts_submitted"),
        "forecasts_resolved": summary.get("forecasts_resolved"),
        "narrative": narrative,
        "brier_note": summary.get("brier_note"),
        "turn_by_turn": summary.get("turn_by_turn", []),
    }


def build_aar_pdf(content: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=1*inch, rightMargin=1*inch)

    styles = getSampleStyleSheet()
    dark_blue = colors.HexColor("#1d4ed8")
    near_black = colors.HexColor("#0a0f1e")
    light_gray = colors.HexColor("#9ca3af")

    title_style = ParagraphStyle("TheaterTitle", parent=styles["Title"],
                                  fontSize=22, textColor=dark_blue, spaceAfter=6, alignment=TA_CENTER)
    h1_style = ParagraphStyle("H1", parent=styles["Heading1"],
                               fontSize=14, textColor=dark_blue, spaceBefore=16, spaceAfter=6)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"],
                               fontSize=11, textColor=colors.HexColor("#374151"), spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("Body", parent=styles["Normal"],
                                 fontSize=9, leading=14, spaceAfter=6)
    class_style = ParagraphStyle("Class", parent=styles["Normal"],
                                  fontSize=10, textColor=colors.black, alignment=TA_CENTER,
                                  backColor=colors.HexColor("#fef9c3"), spaceAfter=8)

    story = []
    metadata = content.get("metadata", {})

    # Classification banner
    story.append(Paragraph("⬛ UNCLASSIFIED // FOR EXERCISE PURPOSES ONLY ⬛", class_style))
    story.append(Spacer(1, 0.1*inch))

    # Title
    title = metadata.get("exercise_title", "After Action Review")
    story.append(Paragraph(f"THEATER WARGAMING PLATFORM", ParagraphStyle("Sub", parent=styles["Normal"],
                            fontSize=10, textColor=light_gray, alignment=TA_CENTER)))
    story.append(Paragraph(title.upper(), title_style))
    story.append(Paragraph("AFTER ACTION REVIEW", ParagraphStyle("Sub2", parent=styles["Normal"],
                            fontSize=12, textColor=dark_blue, alignment=TA_CENTER, spaceAfter=12)))
    story.append(HRFlowable(width="100%", thickness=2, color=dark_blue))
    story.append(Spacer(1, 0.15*inch))

    # Metadata table
    meta_data = [
        ["Exercise Type:", metadata.get("scenario_type", "—"), "Date Generated:", metadata.get("date_generated", "—")],
        ["Duration:", f"{metadata.get('duration_turns', '—')} turns", "Classification:", "UNCLASSIFIED"],
    ]
    meta_table = Table(meta_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    meta_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor("#374151")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.2*inch))

    def add_section(num, title):
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
        story.append(Paragraph(f"SECTION {num}: {title}", h1_style))

    # Section 1: Executive Summary
    s1 = content.get("section_1_executive_summary", {})
    add_section(1, "EXECUTIVE SUMMARY")
    story.append(Paragraph("<b>BLUF:</b> " + s1.get("bottom_line_up_front", ""), body_style))
    story.append(Paragraph("<b>Scenario Overview:</b> " + s1.get("scenario_overview", ""), body_style))
    story.append(Paragraph("<b>Outcome:</b> " + s1.get("outcome", ""), body_style))

    if s1.get("key_findings"):
        story.append(Paragraph("<b>Key Findings:</b>", h2_style))
        for f in s1["key_findings"]:
            story.append(Paragraph(
                f"<b>Finding {f.get('finding_number')} [{f.get('confidence','?')} Confidence — {f.get('significance','?')}]:</b> {f.get('finding','')}",
                body_style
            ))

    # Section 2: Chronological Narrative
    s2 = content.get("section_2_chronological_narrative", {})
    add_section(2, "CHRONOLOGICAL NARRATIVE")
    for phase in s2.get("phase_narratives", []):
        story.append(Paragraph(phase.get("phase", ""), h2_style))
        story.append(Paragraph(phase.get("narrative", ""), body_style))
        if phase.get("turning_point"):
            story.append(Paragraph(f"<i>Turning Point: {phase['turning_point']}</i>", body_style))

    # Section 3: Blue Force Analysis
    s3 = content.get("section_3_blue_force_analysis", {})
    add_section(3, "BLUE FORCE ANALYSIS")
    story.append(Paragraph(f"<b>Overall Grade: {s3.get('overall_grade','—')}</b>", h2_style))
    story.append(Paragraph(f"<b>COA Assessment:</b> {s3.get('coa_assessment','')}", body_style))
    story.append(Paragraph(f"<b>Execution Quality:</b> {s3.get('execution_quality','')}", body_style))
    story.append(Paragraph(f"<b>Logistics/Sustainment:</b> {s3.get('logistics_sustainment','')}", body_style))

    # Section 4: Red Force Analysis
    s4 = content.get("section_4_red_force_analysis", {})
    add_section(4, "RED FORCE ANALYSIS")
    story.append(Paragraph(s4.get("strategy_assessment",""), body_style))
    if s4.get("most_effective_ttps"):
        story.append(Paragraph("<b>Most Effective TTPs:</b>", h2_style))
        for t in s4["most_effective_ttps"]:
            story.append(Paragraph(f"• {t}", body_style))

    # Section 5: Lessons Learned
    s5 = content.get("section_5_lessons_learned", [])
    add_section(5, "LESSONS LEARNED")
    for lesson in s5:
        story.append(Paragraph(
            f"<b>LL-{lesson.get('lesson_number','?')} [{lesson.get('warfighting_function','?')}]</b>",
            h2_style
        ))
        story.append(Paragraph(f"<b>Observation:</b> {lesson.get('observation','')}", body_style))
        story.append(Paragraph(f"<b>Lesson:</b> {lesson.get('lesson_learned','')}", body_style))
        story.append(Paragraph(f"<b>Recommendation:</b> {lesson.get('recommendation','')}", body_style))

    # Section 6: Implications
    s6 = content.get("section_6_implications", {})
    add_section(6, "IMPLICATIONS & RECOMMENDATIONS")
    story.append(Paragraph(f"<b>Doctrine Implications:</b> {s6.get('doctrine_implications','')}", body_style))
    for rec in s6.get("planning_recommendations", []):
        story.append(Paragraph(f"• {rec}", body_style))

    # Section 8: Forecasting Accuracy (optional — only present when forecasting was enabled)
    s8 = content.get("section_8_forecasting_accuracy")
    if s8:
        add_section(8, "FORECASTING ACCURACY")
        avg = s8.get("average_brier_score")
        avg_txt = f"{avg:.3f}" if isinstance(avg, (int, float)) else "—"
        story.append(Paragraph(
            f"<b>Average Brier Score:</b> {_esc(avg_txt)} &nbsp;&nbsp; "
            f"<b>Calibration:</b> {_esc(s8.get('calibration_rating', '—'))}", h2_style))
        story.append(Paragraph(_esc(s8.get("narrative", "")), body_style))
        rows = [["Turn", "P(Blue)", "Blue", "P(Red)", "Red", "P(Esc)", "Esc", "P(Obj)", "Obj", "Brier"]]
        for t in s8.get("turn_by_turn", []):
            def _p(v):
                return f"{float(v):.2f}" if isinstance(v, (int, float)) else "—"
            def _b(v):
                return "✓" if v else ("✗" if v is not None else "—")
            br = t.get("brier_score")
            rows.append([
                str(t.get("turn_num", "—")),
                _p(t.get("p_blue_wins")), _b(t.get("blue_achieved")),
                _p(t.get("p_red_wins")), _b(t.get("red_achieved")),
                _p(t.get("p_escalation")), _b(t.get("escalation_occurred")),
                _p(t.get("p_key_objective_captured")), _b(t.get("key_objective_captured")),
                f"{br:.3f}" if isinstance(br, (int, float)) else "—",
            ])
        f_table = Table(rows, hAlign="LEFT")
        f_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#374151")),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(f_table)
        if s8.get("brier_note"):
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(f"<i>{_esc(s8['brier_note'])}</i>", ParagraphStyle(
                "FNote", parent=body_style, fontSize=8, textColor=colors.HexColor("#6b7280"))))

    # Footer
    story.append(Spacer(1, 0.3*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=dark_blue))
    story.append(Paragraph("THEATER Wargaming Platform — Generated by AI | UNCLASSIFIED",
                            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7,
                                          textColor=light_gray, alignment=TA_CENTER)))

    doc.build(story)
    return buffer.getvalue()


# ===========================================================================
# Briefing Export — deterministic analyst memo (no LLM); see backend/briefing.py
# ===========================================================================

def _gather_adjudication_rows(session: models.GameSession, db: Session) -> list:
    """Briefing source rows from the AdjudicationLog audit trail.

    Falls back to TurnLog.adjudication when a session has no AdjudicationLog rows
    (e.g. the seeded demo): the timeline still renders, but without pre-turn
    unit_status snapshots there are no strength deltas, so turning points come back
    empty and state evolution collapses to the final snapshot.
    """
    logs = (
        db.query(models.AdjudicationLog)
        .filter(models.AdjudicationLog.session_id == session.id)
        .order_by(models.AdjudicationLog.timestamp)
        .all()
    )
    rows = []
    for lg in logs:
        outcome = json.loads(lg.turn_outcome or "{}")
        inputs = json.loads(lg.ai_inputs or "{}")
        rows.append({
            "turn_number": outcome.get("turn_number") or inputs.get("turn_number") or 0,
            "ai_inputs": inputs,
            "turn_outcome": outcome,
        })
    if rows:
        return rows

    # Fallback: reconstruct minimal rows from TurnLog.
    for t in session.turn_logs:
        rows.append({
            "turn_number": t.turn_number,
            "ai_inputs": {
                "unit_status": [],
                "blue_moves": json.loads(t.player_moves or "[]"),
                "red_moves": json.loads(t.ai_moves or "[]"),
            },
            "turn_outcome": json.loads(t.adjudication or "{}"),
        })
    return rows


def _build_session_briefing(session_id: str, db: Session) -> dict:
    """Gather a session's data and compute the deterministic briefing dict."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    scenario_obj = db.query(models.Scenario).filter(
        models.Scenario.id == session.scenario_id
    ).first()
    scenario = {
        "title": scenario_obj.title if scenario_obj else "Untitled Scenario",
        "scenario_type": scenario_obj.scenario_type if scenario_obj else "—",
        "classification": getattr(scenario_obj, "classification", "UNCLASSIFIED") if scenario_obj else "UNCLASSIFIED",
        "factions": json.loads(scenario_obj.factions or "[]") if scenario_obj else [],
        "win_conditions": json.loads(scenario_obj.win_conditions or "{}") if scenario_obj else {},
    }

    final_state = json.loads(session.current_game_state or "{}")
    adjudication_rows = _gather_adjudication_rows(session, db)

    session_meta = {
        "session_id": session.id,
        "session_title": session.title,
        "status": session.status,
        "current_turn": session.current_turn,
        "max_turns": session.max_turns,
    }

    forecasts = None
    if session.forecasting_enabled:
        forecasts = db.query(models.TurnForecast).filter(
            models.TurnForecast.session_id == session.id
        ).all()

    return briefing.build_briefing(
        scenario=scenario,
        adjudication_rows=adjudication_rows,
        final_state=final_state,
        session_meta=session_meta,
        forecasts=forecasts,
    )


@router.get("/{session_id}/briefing-export")
async def get_briefing_export(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Structured analyst briefing for a session (JSON)."""
    return _build_session_briefing(session_id, db)


@router.get("/{session_id}/briefing-export/markdown")
async def get_briefing_export_markdown(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Briefing rendered as Markdown."""
    data = _build_session_briefing(session_id, db)
    md = briefing.briefing_to_markdown(data)
    title = (data.get("metadata", {}).get("scenario_title") or "briefing")
    filename = f"THEATER_briefing_{title.replace(' ', '_')[:30]}.md"
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/briefing-export/pdf")
async def get_briefing_export_pdf(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Briefing rendered as a formatted PDF."""
    data = _build_session_briefing(session_id, db)
    pdf_bytes = build_briefing_pdf(data)
    title = (data.get("metadata", {}).get("scenario_title") or "briefing")
    filename = f"THEATER_briefing_{title.replace(' ', '_')[:30]}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _calibration_chart(turn_calibration: list) -> Drawing:
    """Grouped bar chart: mean forecast estimate vs actual outcome rate, per turn (%).

    A well-calibrated forecaster's blue (estimate) and green (actual) bars sit at the
    same height each turn. Returns a reportlab Drawing.
    """
    turns = [t.get("turn_num") for t in turn_calibration]
    estimates = [round((t.get("mean_estimate") or 0) * 100) for t in turn_calibration]
    actuals = [round((t.get("actual_rate") or 0) * 100) for t in turn_calibration]

    drawing = Drawing(440, 215)
    chart = VerticalBarChart()
    chart.x = 35
    chart.y = 25
    chart.width = 375
    chart.height = 150
    chart.data = [estimates, actuals]
    chart.categoryAxis.categoryNames = [f"T{t}" for t in turns]
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueStep = 25
    chart.valueAxis.labels.fontSize = 8
    chart.bars[0].fillColor = colors.HexColor("#2563eb")  # mean estimate
    chart.bars[1].fillColor = colors.HexColor("#16a34a")  # actual rate
    chart.barWidth = 5
    chart.groupSpacing = 12
    chart.barSpacing = 1
    drawing.add(chart)

    legend = Legend()
    legend.x = 35
    legend.y = 200
    legend.deltax = 140
    legend.fontSize = 8
    legend.alignment = "right"
    legend.columnMaximum = 1
    legend.colorNamePairs = [
        (colors.HexColor("#2563eb"), "Mean estimate %"),
        (colors.HexColor("#16a34a"), "Actual rate %"),
    ]
    drawing.add(legend)
    return drawing


def build_briefing_pdf(data: dict) -> bytes:
    """Render the briefing dict to a PDF. Mirrors build_aar_pdf's visual language;
    every dynamic string is routed through _esc() so special characters cannot
    break reportlab's paragraph markup."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch,
                            bottomMargin=0.75 * inch, leftMargin=1 * inch, rightMargin=1 * inch)

    styles = getSampleStyleSheet()
    dark_blue = colors.HexColor("#1d4ed8")
    light_gray = colors.HexColor("#9ca3af")

    title_style = ParagraphStyle("BriefTitle", parent=styles["Title"], fontSize=22,
                                 textColor=dark_blue, spaceAfter=6, alignment=TA_CENTER)
    h1_style = ParagraphStyle("BH1", parent=styles["Heading1"], fontSize=14,
                              textColor=dark_blue, spaceBefore=16, spaceAfter=6)
    h2_style = ParagraphStyle("BH2", parent=styles["Heading2"], fontSize=11,
                              textColor=colors.HexColor("#374151"), spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("BBody", parent=styles["Normal"], fontSize=9,
                                leading=14, spaceAfter=6)
    class_style = ParagraphStyle("BClass", parent=styles["Normal"], fontSize=10,
                                 textColor=colors.black, alignment=TA_CENTER,
                                 backColor=colors.HexColor("#fef9c3"), spaceAfter=8)

    md = data.get("metadata", {})
    story = []

    # Cover / classification
    classification = md.get("classification", "UNCLASSIFIED")
    story.append(Paragraph(f"⬛ {_esc(classification)} // FOR EXERCISE PURPOSES ONLY ⬛", class_style))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("THEATER WARGAMING PLATFORM", ParagraphStyle(
        "BSub", parent=styles["Normal"], fontSize=10, textColor=light_gray, alignment=TA_CENTER)))
    story.append(Paragraph(_esc(md.get("scenario_title", "Briefing")).upper(), title_style))
    story.append(Paragraph("INTELLIGENCE BRIEFING", ParagraphStyle(
        "BSub2", parent=styles["Normal"], fontSize=12, textColor=dark_blue,
        alignment=TA_CENTER, spaceAfter=12)))
    story.append(HRFlowable(width="100%", thickness=2, color=dark_blue))
    story.append(Spacer(1, 0.15 * inch))

    # Metadata table
    meta_rows = [
        ["Exercise Type:", _esc(md.get("scenario_type", "—")), "Turns Played:", str(md.get("turns_played", 0))],
        ["Outcome:", _esc(data.get("outcome", "—")), "Status:", _esc(md.get("status", "—"))],
    ]
    meta_table = Table(meta_rows, colWidths=[1.5 * inch, 2 * inch, 1.5 * inch, 2 * inch])
    meta_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#374151")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.2 * inch))

    def section(title):
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
        story.append(Paragraph(_esc(title), h1_style))

    # Executive summary
    section("EXECUTIVE SUMMARY")
    story.append(Paragraph(_esc(data.get("executive_summary", "")), body_style))
    metric_note = md.get("strength_metric_note")
    if metric_note:
        story.append(Paragraph(f"<i>{_esc(metric_note)}</i>", ParagraphStyle(
            "BNote", parent=body_style, fontSize=8, textColor=colors.HexColor("#6b7280"))))

    # Outcome
    section("OUTCOME")
    story.append(Paragraph(f"<b>{_esc(data.get('outcome', '—'))}</b>", h2_style))
    story.append(Paragraph(_esc(data.get("outcome_narrative", "")), body_style))

    # Turning points
    section("TURNING POINTS")
    tps = data.get("turning_points", [])
    if tps:
        for tp in tps:
            story.append(Paragraph(
                f"<b>Turn {_esc(tp.get('turn_number'))} — {_esc(tp.get('impact_on_outcome', ''))}</b>",
                h2_style))
            story.append(Paragraph(_esc(tp.get("description", "")), body_style))
            story.append(Paragraph(f"<i>{_esc(tp.get('why_significant', ''))}</i>", body_style))
    else:
        story.append(Paragraph("No turning points detected from the adjudication record.", body_style))

    # Timeline with state evolution
    section("DECISION TIMELINE")
    for t in data.get("timeline", []):
        story.append(Paragraph(f"<b>Turn {_esc(t.get('turn_number'))}</b>", h2_style))
        sc = t.get("state_changes", {})
        story.append(Paragraph(
            f"Strength delta — Blue {_esc(sc.get('blue_strength_delta'))}, "
            f"Red {_esc(sc.get('red_strength_delta'))}", body_style))
        if t.get("adjudication_summary"):
            story.append(Paragraph(_esc(t["adjudication_summary"]), body_style))
        for kd in t.get("key_decisions", []):
            story.append(Paragraph(f"• {_esc(kd)}", body_style))

    # Forecasting accuracy (optional — only when ≥1 forecast has been resolved)
    fcast = data.get("forecasting_accuracy")
    if fcast:
        section("FORECASTING ACCURACY")
        overall = fcast.get("overall_brier_score")
        overall_txt = f"{overall:.3f}" if isinstance(overall, (int, float)) else "—"
        story.append(Paragraph(f"<b>Overall Brier:</b> {_esc(overall_txt)}", h2_style))
        story.append(Paragraph(_esc(fcast.get("calibration_summary", "")), body_style))

        # Calibration chart: mean estimate vs actual rate per turn. Wrapped so a chart
        # failure degrades to the tables rather than breaking the whole export.
        tc = fcast.get("turn_calibration", [])
        if tc:
            try:
                story.append(_calibration_chart(tc))
                story.append(Paragraph(
                    "<i>Blue = mean forecast probability; green = actual outcome rate, per turn. "
                    "Equal-height bars indicate good calibration.</i>",
                    ParagraphStyle("BCap", parent=body_style, fontSize=8,
                                   textColor=colors.HexColor("#6b7280"))))
            except Exception:
                pass

        # Notable mispredictions table
        notable = fcast.get("notable_mispredictions", [])
        story.append(Paragraph("Notable Mispredictions", h2_style))
        if notable:
            m_rows = [["Turn", "Question", "Estimate", "Outcome", "Brier"]]
            for m in notable:
                est = m.get("estimate")
                m_rows.append([
                    str(m.get("turn_num", "—")),
                    _esc(m.get("question", "—")),
                    f"{est*100:.0f}%" if isinstance(est, (int, float)) else "—",
                    "occurred" if m.get("outcome") else "did not occur",
                    str(m.get("brier_component", "—")),
                ])
            m_table = Table(m_rows, hAlign="LEFT", colWidths=[0.5*inch, 2.4*inch, 0.9*inch, 1.2*inch, 0.7*inch])
            m_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#374151")),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(m_table)
        else:
            story.append(Paragraph("None — no confidently-wrong forecasts.", body_style))

        if fcast.get("methodology_note"):
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(f"<i>{_esc(fcast['methodology_note'])}</i>", ParagraphStyle(
                "BFNote", parent=body_style, fontSize=8, textColor=colors.HexColor("#6b7280"))))

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=dark_blue))
    story.append(Paragraph(
        f"THEATER Wargaming Platform — Deterministic Briefing | {_esc(classification)}",
        ParagraphStyle("BFooter", parent=styles["Normal"], fontSize=7,
                       textColor=light_gray, alignment=TA_CENTER)))

    doc.build(story)
    return buffer.getvalue()
