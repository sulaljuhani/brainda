from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user, get_db
from api.models.document import SearchResponse
from api.services.vector_service import VectorService

router = APIRouter(prefix="/api/v1", tags=["search"])


async def _keyword_document_matches(
    db,
    user_id: UUID,
    query: str,
    limit: int,
) -> List[dict]:
    """Return simple keyword matches from filenames or chunk text."""
    term = query.strip()
    if len(term) < 3:
        return []

    like_pattern = f"%{term}%"
    rows = await db.fetch(
        """
        SELECT
            d.id,
            d.filename,
            d.updated_at,
            snippet.text AS snippet
        FROM documents d
        LEFT JOIN LATERAL (
            SELECT text
            FROM chunks c
            WHERE c.document_id = d.id
            ORDER BY c.ordinal ASC
            LIMIT 1
        ) AS snippet ON TRUE
        WHERE d.user_id = $1
          AND d.status = 'indexed'
          AND (
            d.filename ILIKE $2
            OR EXISTS (
                SELECT 1
                FROM chunks c2
                WHERE c2.document_id = d.id
                  AND c2.text ILIKE $2
            )
          )
        ORDER BY d.updated_at DESC
        LIMIT $3
        """,
        user_id,
        like_pattern,
        max(limit, 5),
    )

    keyword_results: List[dict] = []
    for row in rows:
        excerpt = (row["snippet"] or "").strip()
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "..."
        keyword_results.append(
            {
                "id": str(row["id"]),
                "content_type": "document_chunk",
                "title": row["filename"],
                "excerpt": excerpt,
                "score": 1.0,
                "payload": {"user_id": str(user_id)},
                "metadata": {
                    "chunk_index": 0,
                    "page": None,
                    "parent_document_id": str(row["id"]),
                    "created_at": row["updated_at"].isoformat() + "Z"
                    if row["updated_at"]
                    else None,
                },
            }
        )
    return keyword_results


@router.get("/search", response_model=SearchResponse)
async def search_knowledge_base(
    q: str = Query(..., description="Search query"),
    content_type: Optional[str] = Query(
        None, description="Filter by content type: note, document_chunk, or all"
    ),
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(
        0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (cosine distance).",
    ),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    vector_service = VectorService()
    requested_filter = content_type
    if requested_filter in ("all", ""):
        requested_filter = None
    elif requested_filter == "document":
        requested_filter = "document_chunk"

    vector_results = await vector_service.search(
        query=q,
        user_id=user_id,
        content_type=requested_filter,
        limit=limit,
        min_score=min_score,
    )

    include_documents = requested_filter in (None, "document_chunk")
    keyword_results: List[dict] = []
    if include_documents:
        keyword_results = await _keyword_document_matches(db, user_id, q, limit)

    combined = keyword_results + vector_results
    deduped: List[dict] = []
    seen = set()
    for item in combined:
        key = (item.get("content_type"), item.get("id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    if len(deduped) > limit:
        deduped = deduped[:limit]

    return {"results": deduped, "query": q, "total": len(deduped)}
