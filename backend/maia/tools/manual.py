"""Search the maintenance manual by meaning (retrieval for RAG)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from maia.db.models import ManualChunk
from maia.manual.embeddings import Embedder
from maia.tools.errors import ToolError
from maia.tools.schemas import ManualHit


def search_manual(
    session: Session, embedder: Embedder, query: str, limit: int = 3
) -> list[ManualHit]:
    """Return the manual sections closest in meaning to the query, best first. The agent
    quotes limits only from these results and cites their section code."""
    if not query.strip():
        raise ToolError("The search query is empty.")

    query_vector = embedder.embed([query])[0]
    distance = ManualChunk.embedding.cosine_distance(query_vector)
    rows = session.execute(
        select(ManualChunk, distance)
        .where(ManualChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    ).all()
    if not rows:
        raise ToolError("The manual has not been loaded. Run: python -m maia.manual.ingest")

    return [
        ManualHit(
            section_code=chunk.section_code,
            title=chunk.title,
            content=chunk.content,
            similarity=round(1 - float(dist), 3),
        )
        for chunk, dist in rows
    ]
