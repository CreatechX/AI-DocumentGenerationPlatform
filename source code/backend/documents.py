from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.core.deps import get_current_user
from app.models.document import DocumentRecord
from app.models.user import User
from app.schemas.document import DocumentResponse, GenerateDocumentRequest, UploadResponse
from app.services.document_ingestion import extract_text
from app.services.document_service import DocumentService
from app.services.external_info_service import ExternalInfoService
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService
from app.utils.file_sanitizer import ensure_user_dirs, safe_filename

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_UPLOAD_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".txt"})

ollama_service = OllamaService()
rag_service = RagService()
doc_service = DocumentService()
external_service = ExternalInfoService()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    original_name = file.filename or "upload.txt"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )

    dirs = ensure_user_dirs(settings.storage_root, current_user.id)
    original_safe = safe_filename(original_name)
    original_path = dirs["uploads"] / original_safe
    original_path.write_bytes(raw)

    text = await extract_text(str(original_path), ext)
    stem = Path(original_safe).stem
    indexed_name = safe_filename(f"{stem}_indexed_{uuid4().hex[:8]}.txt")
    buf = BytesIO(text.encode("utf-8"))
    buf.seek(0)
    synthetic = UploadFile(file=buf, filename=indexed_name)
    _, count = await rag_service.index_uploaded_file(current_user.id, synthetic)

    return UploadResponse(filename=original_safe, chunks_indexed=count)


@router.post("/generate", response_model=DocumentResponse)
async def generate_document(
    payload: GenerateDocumentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    context_chunks = rag_service.retrieve_context(current_user.id, payload.prompt, n_results=5)
    latest_info = ""
    if payload.use_external_latest_info:
        latest_info = await external_service.fetch_latest(payload.prompt)

    generation_prompt = (
        f"Tone: {payload.tone}\n"
        f"Format: {payload.format_style}\n"
        f"Requested output type: {payload.output_type}\n"
        f"User prompt: {payload.prompt}\n"
    )
    if latest_info:
        generation_prompt += f"\nLatest public info (question-only fetch):\n{latest_info}"

    content = await ollama_service.generate_text(generation_prompt, context_chunks=context_chunks)
    output_path = doc_service.save_generated(current_user.id, payload.title, payload.output_type, content)

    record = DocumentRecord(
        user_id=current_user.id,
        title=payload.title,
        output_type=payload.output_type,
        prompt=payload.prompt,
        file_path=str(output_path),
        preview_text=content[:4000],
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return DocumentResponse(
        id=record.id,
        title=record.title,
        output_type=record.output_type,
        preview_text=record.preview_text,
        created_at=record.created_at,
    )


@router.get("/history", response_model=list[DocumentResponse])
async def get_history(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    result = await db.execute(
        select(DocumentRecord)
        .where(DocumentRecord.user_id == current_user.id)
        .order_by(desc(DocumentRecord.created_at))
    )
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=doc.id,
            title=doc.title,
            output_type=doc.output_type,
            preview_text=doc.preview_text,
            created_at=doc.created_at,
        )
        for doc in docs
    ]


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DocumentRecord).where(
            DocumentRecord.id == document_id,
            DocumentRecord.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")
    return FileResponse(path, filename=path.name)
