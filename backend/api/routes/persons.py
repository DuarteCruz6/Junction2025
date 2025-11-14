"""
Person detection endpoints
"""

from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/api/persons/detect")
async def detect_person(image: UploadFile):
    """Detect and identify person in image"""
    # TODO: Implement person detection and identification
    # person_id = await detect_and_identify_person(image)
    
    return JSONResponse(content={
        "person_id": None,
        "name": None,
        "confidence": 0.0,
        "is_known": False,
    })

