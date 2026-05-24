from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List

from src.config import get_markdown_docs
from src.models import SourceChunk


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _clean_heading(text: str) -> str:
    return re.sub(r"[*_`]", "", text).strip()


def _document_id(path: Path) -> str:
    return path.stem.replace("_", "-")


def parse_markdown_file(path: Path) -> List[SourceChunk]:
    lines = path.read_text(encoding="utf-8").splitlines()
    headings = []

    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), _clean_heading(match.group(2))))

    if not headings:
        text = "\n".join(lines).strip()
        return [
            SourceChunk(
                id=f"{path.stem}:1",
                text=text,
                source_file=path.name,
                section_heading=path.stem,
                section_path=path.stem,
                start_line=1,
                end_line=len(lines),
                document_id=_document_id(path),
            )
        ]

    chunks: List[SourceChunk] = []
    stack: List[tuple[int, str]] = []

    for pos, (start, level, heading) in enumerate(headings):
        end = headings[pos + 1][0] - 1 if pos + 1 < len(headings) else len(lines)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading))
        section_path = " > ".join(item[1] for item in stack)
        text = "\n".join(lines[start - 1 : end]).strip()
        is_security_test = (
            path.name == "shipment_escalation_sop.md"
            and "prompt injection" in section_path.lower()
        )
        chunk_id = f"{path.stem}:{start}:{re.sub(r'[^a-zA-Z0-9]+', '-', section_path).strip('-').lower()}"
        chunks.append(
            SourceChunk(
                id=chunk_id,
                text=text,
                source_file=path.name,
                section_heading=heading,
                section_path=section_path,
                start_line=start,
                end_line=end,
                document_id=_document_id(path),
                security_test_artifact=is_security_test,
            )
        )

    return chunks


def load_markdown_chunks(paths: Iterable[Path] | None = None) -> List[SourceChunk]:
    chunks: List[SourceChunk] = []
    for path in paths or get_markdown_docs():
        chunks.extend(parse_markdown_file(path))
    return chunks


if __name__ == "__main__":
    for chunk in load_markdown_chunks():
        print(f"{chunk.id}\t{chunk.source_file}\t{chunk.section_path}\t{chunk.start_line}-{chunk.end_line}")
