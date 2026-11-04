"""Load the manual into the database with its embeddings.

Usage:
    uv run python -m maia.manual.ingest
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from maia.db.models import ManualChunk
from maia.db.session import get_sessionmaker
from maia.manual.chunking import Section, load_manual
from maia.manual.embeddings import Embedder, LiteLLMEmbedder

logger = logging.getLogger(__name__)


def ingest_manual(session: Session, embedder: Embedder, sections: list[Section]) -> int:
    """Insert or update one row per section. Safe to run again after editing the manual."""
    vectors = embedder.embed([s.text_for_embedding for s in sections])
    for section, vector in zip(sections, vectors, strict=True):
        chunk = session.scalar(select(ManualChunk).where(ManualChunk.section_code == section.code))
        if chunk is None:
            chunk = ManualChunk(section_code=section.code)
            session.add(chunk)
        chunk.title = section.title
        chunk.content = section.content
        chunk.embedding = vector
    session.flush()
    return len(sections)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with get_sessionmaker()() as session, session.begin():
        count = ingest_manual(session, LiteLLMEmbedder(), load_manual())
    logger.info("Loaded %d manual sections.", count)


if __name__ == "__main__":
    main()
