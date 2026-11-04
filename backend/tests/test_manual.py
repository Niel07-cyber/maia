import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from maia.db.models import ManualChunk
from maia.manual.chunking import load_manual, split_sections
from maia.manual.embeddings import Embedder
from maia.manual.ingest import ingest_manual
from maia.tools.errors import ToolError
from maia.tools.manual import search_manual


def test_manual_is_split_into_its_eight_sections() -> None:
    codes = [section.code for section in load_manual()]

    assert codes == [
        "SAF-01",
        "SAF-02",
        "PROC-BRK-01",
        "PROC-WHL-02",
        "PROC-PAN-03",
        "PROC-BAT-04",
        "PROC-DOR-05",
        "GLO-01",
    ]


def test_each_procedure_keeps_its_limits_in_the_same_chunk() -> None:
    brake = next(s for s in load_manual() if s.code == "PROC-BRK-01")

    assert brake.title == "Brake pad inspection (bogie)"
    assert "minimum limit 5 mm" in brake.content
    assert "BP-2207" in brake.content


def test_split_ignores_text_before_the_first_section() -> None:
    sections = split_sections("# Title\nIntro text\n## SAF-01 Safety\nWear gloves.\n")

    assert len(sections) == 1
    assert sections[0].content == "Wear gloves."


def test_ingest_is_idempotent(db_session: Session, embedder: Embedder) -> None:
    ingest_manual(db_session, embedder, load_manual())
    ingest_manual(db_session, embedder, load_manual())

    count = db_session.scalar(select(func.count()).select_from(ManualChunk))
    assert count == 8


def test_search_finds_the_brake_procedure(db_session: Session, embedder: Embedder) -> None:
    ingest_manual(db_session, embedder, load_manual())

    hits = search_manual(db_session, embedder, "brake pad thickness minimum limit")

    assert hits[0].section_code == "PROC-BRK-01"
    assert hits[0].similarity > hits[-1].similarity


def test_search_before_ingest_explains_what_to_do(db_session: Session, embedder: Embedder) -> None:
    with pytest.raises(ToolError, match="not been loaded"):
        search_manual(db_session, embedder, "brake pads")


def test_search_rejects_an_empty_query(db_session: Session, embedder: Embedder) -> None:
    with pytest.raises(ToolError, match="empty"):
        search_manual(db_session, embedder, "   ")
