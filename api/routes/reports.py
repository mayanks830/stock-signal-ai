import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from config import PDF_OUTPUT_DIR

router = APIRouter()


@router.get("/reports")
def list_reports():
    """List all PDF reports sorted newest first."""
    if not os.path.exists(PDF_OUTPUT_DIR):
        return []

    reports = []
    for fname in os.listdir(PDF_OUTPUT_DIR):
        if not fname.lower().endswith(".pdf"):
            continue
        fpath = os.path.join(PDF_OUTPUT_DIR, fname)
        stat = os.stat(fpath)
        reports.append({
            "filename": fname,
            "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "size_kb": round(stat.st_size / 1024, 1),
        })

    reports.sort(key=lambda r: r["date"], reverse=True)
    return reports


@router.get("/reports/{filename}")
def download_report(filename: str):
    """Serve a PDF report for download."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    fpath = os.path.join(PDF_OUTPUT_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(fpath, media_type="application/pdf", filename=filename)
