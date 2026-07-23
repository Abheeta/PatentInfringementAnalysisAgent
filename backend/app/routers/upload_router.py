from fastapi import APIRouter, File, Form, UploadFile

from app.config import settings
from app.errors import ApiError
from app.services import chart_service, evidence_service

router = APIRouter(tags=["upload"])


@router.post("/session/{sid}/upload-chart", status_code=204)
async def upload_chart(sid: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise ApiError(400, "invalid_file_type", "Only .csv files are accepted.")

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_BYTES:
        raise ApiError(400, "file_too_large", "File exceeds the 5MB limit.")

    chart_service.parse_chart_csv(sid, contents)


@router.post("/session/{sid}/upload-evidence", status_code=204)
async def upload_evidence(
    sid: str,
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
):
    has_file = file is not None and file.filename
    has_url = url is not None and url.strip() != ""

    if has_file == has_url:
        raise ApiError(
            400, "invalid_request", "Provide exactly one of file or url."
        )

    if has_file:
        if not file.filename.lower().endswith(".txt"):
            raise ApiError(400, "invalid_file_type", "Only .txt files are accepted.")
        contents = await file.read()
        if len(contents) > settings.MAX_UPLOAD_BYTES:
            raise ApiError(
                400,
                "file_too_large",
                f"'{file.filename}' exceeds the 5MB limit.",
            )
        try:
            text = contents.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ApiError(400, "invalid_file_type", "Only .txt files are accepted.")
        evidence_service.store_uploaded_text(sid, file.filename, text)
    else:
        evidence_service.fetch_url(sid, url)
