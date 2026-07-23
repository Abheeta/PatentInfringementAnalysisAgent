from fastapi import APIRouter, Response

from app.services import export_service

router = APIRouter(tags=["export"])


@router.get("/session/{sid}/export")
def export_chart(sid: str):
    content = export_service.build_docx(sid)
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": 'attachment; filename="claim_chart.docx"'
        },
    )
