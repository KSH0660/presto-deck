import os
from fastapi import APIRouter, HTTPException
from typing import List

router = APIRouter()

TEMPLATE_DIR = os.path.join("presto", "templates")

@router.get("/themes", response_model=List[str])
def get_available_themes():
    """Scans the templates directory and returns a list of available theme names."""
    try:
        if not os.path.isdir(TEMPLATE_DIR):
            raise HTTPException(status_code=404, detail="Templates directory not found.")
        
        themes = [d for d in os.listdir(TEMPLATE_DIR) if os.path.isdir(os.path.join(TEMPLATE_DIR, d))]
        # Filter out any directories that might start with . or _
        themes = [d for d in themes if not d.startswith(('.', '_'))]
        
        return sorted(themes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while scanning themes: {str(e)}")
