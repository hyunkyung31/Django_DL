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
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from api.media_utils import download_media_bytes
from api.models import Doctor, EMRSignOff, Examination, Patient


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


def _safe_text(value: Any, default: str = "-") -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _format_boolean(value: Any) -> str:
    if value is True:
        return "예"

    if value is False:
        return "아니오"

    return "-"


def _format_percent(value: Any) -> str:
    if value is None:
        return "-"

    try:
        number = float(value)

        if 0 <= number <= 1:
            number *= 100

        return f"{number:.2f}%"
    except (TypeError, ValueError):
        return _safe_text(value)


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
        ),
        "body": ParagraphStyle(
            "ClinicalReportBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=14,
        ),
        "small": ParagraphStyle(
            "ClinicalReportSmall",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8,
            leading=11,
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


def _load_report_image(
    stored_path: str | None,
    max_width_mm: float = 160,
    max_height_mm: float = 90,
) -> Image | None:
    if not stored_path:
        return None

    try:
        content, _, _ = download_media_bytes(
            stored_path,
        )
    except (FileNotFoundError, OSError):
        return None

    image_buffer = io.BytesIO(content)

    try:
        report_image = Image(image_buffer)
    except Exception:
        return None

    max_width = max_width_mm * mm
    max_height = max_height_mm * mm

    width_ratio = max_width / report_image.imageWidth
    height_ratio = max_height / report_image.imageHeight
    scale = min(
        width_ratio,
        height_ratio,
        1,
    )

    report_image.drawWidth = (
        report_image.imageWidth * scale
    )
    report_image.drawHeight = (
        report_image.imageHeight * scale
    )
    report_image.hAlign = "CENTER"

    return report_image


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
            "VENA 관상동맥 AI 임상 보고서",
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
        Spacer(1, 8 * mm),
        Paragraph(
            "환자 정보",
            styles["section"],
        ),
        _build_info_table(
            [
                ("환자 ID", patient.patient_id),
                ("환자명", patient.patient_name),
                ("성별", patient.gender),
                ("나이", patient.age),
                ("주호소", patient.chief_complaint),
                ("심전도 결과", patient.ecg_result),
                ("Troponin-T", patient.troponin_t_level),
                ("위험인자 수", patient.risk_factors_count),
            ],
            styles,
        ),
        Paragraph(
            "검사 정보",
            styles["section"],
        ),
        _build_info_table(
            [
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
            "AI 분석 결과",
            styles["section"],
        ),
        _build_info_table(
            [
                (
                    "병변 탐지",
                    _format_boolean(
                        ai_result.get("has_lesion")
                    ),
                ),
                (
                    "중증도",
                    ai_result.get("severity_class"),
                ),
                (
                    "신뢰도",
                    _format_percent(
                        ai_result.get("confidence_score")
                    ),
                ),
                (
                    "HEART Score",
                    ai_result.get("heart_score"),
                ),
                (
                    "MACE 위험도",
                    _format_percent(
                        ai_result.get("mace_risk_percent")
                    ),
                ),
            ],
            styles,
        ),
    ]

    key_frame_image = _load_report_image(
        getattr(
            examination,
            "key_frame_path",
            None,
        )
    )

    if key_frame_image is not None:
        story.extend(
            [
                Paragraph(
                    "대표 혈관조영 영상",
                    styles["section"],
                ),
                key_frame_image,
            ]
        )

    gradcam_image = _load_report_image(
        ai_result.get("gradcam_path")
    )

    if gradcam_image is not None:
        story.extend(
            [
                Paragraph(
                    "Grad-CAM 분석 영상",
                    styles["section"],
                ),
                gradcam_image,
            ]
        )

    story.extend(
        [
            PageBreak(),
            Paragraph(
                "최종 의료진 소견",
                styles["section"],
            ),
            _paragraph(
                signoff.final_result,
                styles["body"],
            ),
            Spacer(1, 10 * mm),
            Paragraph(
                "승인 의료진",
                styles["section"],
            ),
            _build_info_table(
                [
                    ("의료진 ID", doctor.doctor_id),
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
            Spacer(1, 12 * mm),
            _paragraph(
                (
                    "본 보고서는 AI 분석 결과를 의료진이 검토하고 "
                    "최종 승인한 임상 지원 문서입니다."
                ),
                styles["small"],
            ),
        ]
    )

    try:
        document.build(story)
    except Exception as exc:
        raise ClinicalReportPdfError(
            "임상 보고서 PDF 생성 중 오류가 발생했습니다."
        ) from exc

    return output.getvalue()