"""API endpoints for document export."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import Run, Section
from services.export_service import (
    PDFExporter,
    DOCXExporter,
    MarkdownExporter,
    CitationStyle,
)

router = APIRouter(prefix="/api/runs", tags=["exports"])


@router.get("/{doc_id}/export/pdf")
async def export_pdf(
    doc_id: str,
    citation_style: CitationStyle = Query(CitationStyle.APA),
    db: AsyncSession = Depends(get_db),
):
    """Export run as PDF document.
    
    Args:
        doc_id: Run document ID
        citation_style: Citation format (APA, MLA, Chicago)
    
    Returns:
        PDF file download
    """
    # Fetch run
    result = await db.execute(select(Run).where(Run.doc_id == doc_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Fetch sections
    result = await db.execute(
        select(Section)
        .where(Section.doc_id == doc_id)
        .order_by(Section.section_idx)
    )
    sections = result.scalars().all()
    
    # Generate PDF
    exporter = PDFExporter(citation_style=citation_style)
    pdf_bytes = exporter.export(run, sections)
    
    # Return as download
    filename = f"{run.topic.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.get("/{doc_id}/export/docx")
async def export_docx(
    doc_id: str,
    citation_style: CitationStyle = Query(CitationStyle.APA),
    db: AsyncSession = Depends(get_db),
):
    """Export run as DOCX document.
    
    Args:
        doc_id: Run document ID
        citation_style: Citation format (APA, MLA, Chicago)
    
    Returns:
        DOCX file download
    """
    # Fetch run and sections
    result = await db.execute(select(Run).where(Run.doc_id == doc_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    result = await db.execute(
        select(Section)
        .where(Section.doc_id == doc_id)
        .order_by(Section.section_idx)
    )
    sections = result.scalars().all()
    
    # Generate DOCX
    exporter = DOCXExporter(citation_style=citation_style)
    docx_bytes = exporter.export(run, sections)
    
    # Return as download
    filename = f"{run.topic.replace(' ', '_')}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(docx_bytes)),
        },
    )


@router.get("/{doc_id}/export/markdown")
async def export_markdown(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Export run as Markdown document.
    
    Args:
        doc_id: Run document ID
    
    Returns:
        Markdown file download
    """
    # Fetch run and sections
    result = await db.execute(select(Run).where(Run.doc_id == doc_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    result = await db.execute(
        select(Section)
        .where(Section.doc_id == doc_id)
        .order_by(Section.section_idx)
    )
    sections = result.scalars().all()
    
    # Generate Markdown
    exporter = MarkdownExporter()
    md_text = exporter.export(run, sections)
    
    # Return as download
    filename = f"{run.topic.replace(' ', '_')}.md"
    return Response(
        content=md_text,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(md_text)),
        },
    )
