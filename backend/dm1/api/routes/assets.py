"""
Asset serving endpoint for DungeonMasterONE.

Serves generated images from the local asset directory.
Production would use cloud storage (S3-compatible).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/assets", tags=["assets"])

ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "campaigns"


@router.get("/campaigns/{campaign_id}/{filename}")
async def get_asset(campaign_id: str, filename: str):
    """Serve a campaign asset (image) by filename."""
    filepath = ASSETS_DIR / campaign_id / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Asset not found")

    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    media_type = "image/jpeg" if filename.endswith(".jpg") else "image/png"
    return FileResponse(filepath, media_type=media_type)
