from fastapi import FastAPI
from app.api.v1 import presentation

app = FastAPI(
    title="Presto API",
    description="AI-powered presentation slide generator.",
    version="1.0.0",
)

app.include_router(presentation.router, prefix="/api/v1")


@app.get("/")
async def read_root():
    """루트 경로 헬스체크"""
    return {"message": "Welcome to Presto API"}
