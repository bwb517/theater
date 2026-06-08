import json
import uuid
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_optional_user
from limiter import limiter
import models
import ai_client
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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
    user=Depends(get_optional_user)
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

    # Footer
    story.append(Spacer(1, 0.3*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=dark_blue))
    story.append(Paragraph("THEATER Wargaming Platform — Generated by AI | UNCLASSIFIED",
                            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7,
                                          textColor=light_gray, alignment=TA_CENTER)))

    doc.build(story)
    return buffer.getvalue()
