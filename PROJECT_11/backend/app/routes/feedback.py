from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()


@router.get("/")
async def feedback_dashboard(request: Request):
    """Feedback dashboard page."""
    return Response("dashboard")


@router.post("/import")
async def feedback_import(request: Request):
    """Import feedback from reviews/surveys."""
    form = await request.form()
    reviews = form.get("reviews")
    if not reviews:
        return Response("Please provide feedback text", status_code=400)
    return Response(f"received: {reviews}")


@router.post("/analyze")
async def feedback_analyze(request: Request):
    """Analyze feedback for sentiment themes."""
    form = await request.form()
    text = form.get("text")
    if not text or not text.strip():
        return Response("Please provide feedback text", status_code=400)
    return Response(f"text: {text}")


@router.post("/pain-points")
async def feedback_pain_points(request: Request):
    """Extract pain points from feedback."""
    form = await request.form()
    reviews = form.get("reviews")
    return Response(f"pain: {reviews}")


@router.post("/feature-requests")
async def feedback_feature_requests(request: Request):
    """Extract feature requests from feedback."""
    form = await request.form()
    reviews = form.get("reviews")
    return Response(f"feature: {reviews}")


@router.post("/list")
async def feedback_list(request: Request):
    """List stored feedback entries."""
    return Response("list")


@router.post("/clear")
async def feedback_clear(request: Request):
    """Clear all stored feedback."""
    return Response("clear")