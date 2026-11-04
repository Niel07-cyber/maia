"""Split the manual into one chunk per section, keyed by its section code."""

import re
from dataclasses import dataclass
from pathlib import Path

MANUAL_PATH = Path(__file__).parent / "rv200_manual.md"

# A section starts with a level-2 heading: "## PROC-BRK-01 Brake pad inspection (bogie)"
_SECTION_HEADING = re.compile(r"^## (?P<code>[A-Z]+-[A-Z0-9-]+) (?P<title>.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Section:
    code: str
    title: str
    content: str

    @property
    def text_for_embedding(self) -> str:
        """Title and body together, so a search for either finds the section."""
        return f"{self.code} {self.title}\n{self.content}"


def split_sections(markdown: str) -> list[Section]:
    """One section per heading. Sections are small and self-contained, so splitting on
    headings keeps each procedure and its limits together in one chunk."""
    headings = list(_SECTION_HEADING.finditer(markdown))
    sections = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown)
        body = markdown[heading.end() : end].strip()
        sections.append(Section(heading["code"], heading["title"].strip(), body))
    return sections


def load_manual() -> list[Section]:
    return split_sections(MANUAL_PATH.read_text(encoding="utf-8"))
