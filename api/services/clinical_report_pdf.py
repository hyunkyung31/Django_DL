from __future__ import annotations

import io
import os
from typing import Any

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from api.models import Doctor, EMRSignOff, Examination, Patient
from api.services.clinical_report_content import (
    build_patient_ai_result_label,
    build_patient_ai_summary,
    build_patient_xai_explanation,
    clean_final_result,
    safe_text,
)


class ClinicalReportPdfError(Exception):
    pass


_REPORT_FONT_NAME = "ClinicalReportKoreanFont"


def _register_report_font() -> str:
    font_path = getattr(
        settings,
        "CLINICAL_REPORT_FONT_PATH",
        "",
    )

    if not font_path:
        raise ClinicalReportPdfError(
            "임상 보고서 한글 글꼴 경로가 설정되지 않았습니다."
        )

    if not os.path.isfile(font_path):
        raise ClinicalReportPdfError(
            "설정된 임상 보고서 한글 글꼴 파일을 찾을 수 없습니다."
        )

    if _REPORT_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(
            TTFont(
                _REPORT_FONT_NAME,
                font_path,
            )
        )

    return _REPORT_FONT_NAME


def _safe_text(
    value: Any,
    default: str = "-",
) -> str:
    return safe_text(value, default=default)


def _build_styles(
    font_name: str,
) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ClinicalReportTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=20,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "ClinicalReportSection",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=18,
            spaceBefore=10,
            spaceAfter=8,
            textColor=colors.HexColor("#183B7A"),
        ),
        "body": ParagraphStyle(
            "ClinicalReportBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=15,
        ),
        "small": ParagraphStyle(
            "ClinicalReportSmall",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
        ),
        "notice": ParagraphStyle(
            "ClinicalReportNotice",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#374151"),
            backColor=colors.HexColor("#F3F6FA"),
            borderColor=colors.HexColor("#D7DEE8"),
            borderWidth=0.5,
            borderPadding=8,
            spaceBefore=8,
        ),
    }


def _paragraph(
    value: Any,
    style: ParagraphStyle,
) -> Paragraph:
    text = _safe_text(value)

    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )

    return Paragraph(text, style)


def _build_info_table(
    rows: list[tuple[str, Any]],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data = [
        [
            _paragraph(label, styles["body"]),
            _paragraph(value, styles["body"]),
        ]
        for label, value in rows
    ]

    table = Table(
        data,
        colWidths=[42 * mm, 128 * mm],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#EAF0F8"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#B8C4D4"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return table


def generate_clinical_report_pdf(
    signoff: EMRSignOff,
) -> bytes:
    if not signoff.finalized:
        raise ClinicalReportPdfError(
            "최종 승인된 임상 보고서만 PDF로 생성할 수 있습니다."
        )

    if not signoff.final_result.strip():
        raise ClinicalReportPdfError(
            "최종 의료진 소견이 없습니다."
        )

    if not signoff.ai_result:
        raise ClinicalReportPdfError(
            "저장된 AI 분석 결과가 없습니다."
        )

    patient = Patient.objects.filter(
        patient_id=signoff.patient_id,
    ).first()

    if patient is None:
        raise ClinicalReportPdfError(
            "환자 정보를 찾을 수 없습니다."
        )

    doctor = Doctor.objects.filter(
        doctor_id=signoff.doctor_id,
    ).first()

    if doctor is None:
        raise ClinicalReportPdfError(
            "승인 의료진 정보를 찾을 수 없습니다."
        )

    ai_result = signoff.ai_result or {}
    exam_id = ai_result.get("exam_id")

    examination = None

    if exam_id is not None:
        examination = Examination.objects.filter(
            exam_id=exam_id,
            patient_id=signoff.patient_id,
        ).first()

    font_name = _register_report_font()
    styles = _build_styles(font_name)
    output = io.BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"VENA 임상 보고서 {signoff.id}",
        author=doctor.doctor_name,
    )

    story = [
        Paragraph(
            "관상동맥 조영술 임상 보고서",
            styles["title"],
        ),
        _paragraph(
            f"보고서 번호: {signoff.id}",
            styles["small"],
        ),
        _paragraph(
            (
                "생성 시각: "
                f"{timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            styles["small"],
        ),
        Spacer(1, 7 * mm),
        Paragraph(
            "환자 및 검사 정보",
            styles["section"],
        ),
        _build_info_table(
            [
                ("환자명", patient.patient_name),
                ("환자 ID", patient.patient_id),
                ("성별", patient.gender),
                ("나이", patient.age),
                ("검사 ID", exam_id),
                (
                    "혈관 유형",
                    getattr(
                        examination,
                        "vessel_type",
                        None,
                    ),
                ),
            ],
            styles,
        ),
        Paragraph(
            "AI 보조 분석 결과",
            styles["section"],
        ),
        _build_info_table(
            [
                (
                    "분석 결과",
                    build_patient_ai_result_label(
                        ai_result
                    ),
                ),
            ],
            styles,
        ),
        Spacer(1, 3 * mm),
        _paragraph(
            build_patient_ai_summary(ai_result),
            styles["body"],
        ),
        Paragraph(
            "AI 분석에 대한 안내",
            styles["section"],
        ),
        _paragraph(
            build_patient_xai_explanation(ai_result),
            styles["body"],
        ),
        Paragraph(
            "의료진 최종 소견",
            styles["section"],
        ),
        _paragraph(
            clean_final_result(signoff.final_result),
            styles["body"],
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            "승인 의료진",
            styles["section"],
        ),
        _build_info_table(
            [
                ("의료진명", doctor.doctor_name),
                ("진료과", doctor.department),
                ("병원", doctor.hospital_name),
                (
                    "최종 승인 시각",
                    timezone.localtime(
                        signoff.updated_at
                    ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                ),
            ],
            styles,
        ),
        Spacer(1, 8 * mm),
        _paragraph(
            (
                "본 보고서의 AI 분석 결과는 의료진의 영상 판독과 "
                "임상적 판단을 보조하기 위한 정보입니다. "
                "AI 분석만으로 질환을 확정하거나 치료 방법을 결정하지 "
                "않으며, 최종 결과와 향후 진료 계획은 담당 의료진과 "
                "상담해 주세요."
            ),
            styles["notice"],
        ),
    ]

    try:
        document.build(story)
    except Exception as exc:
        raise ClinicalReportPdfError(
            "임상 보고서 PDF 생성 중 오류가 발생했습니다."
        ) from exc

    return output.getvalue()