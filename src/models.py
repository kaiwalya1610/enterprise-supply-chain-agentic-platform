from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Citation:
    source_file: str
    section_heading: str
    section_path: str
    start_line: int
    end_line: int


@dataclass
class SourceChunk:
    id: str
    text: str
    source_file: str
    section_heading: str
    section_path: str
    start_line: int
    end_line: int
    document_id: str
    security_test_artifact: bool = False
    score: float = 0.0
    similarity_score: float = 0.0

    def citation(self) -> Citation:
        return Citation(
            source_file=self.source_file,
            section_heading=self.section_heading,
            section_path=self.section_path,
            start_line=self.start_line,
            end_line=self.end_line,
        )


@dataclass
class GraphFact:
    subject: str
    relationship: str
    object: str
    source: str
    subject_type: Optional[str] = None
    object_type: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteDecision:
    route: str
    reason: str
    required_inputs: List[str] = field(default_factory=list)


@dataclass
class RetrievalBundle:
    question: str
    route: str
    doc_chunks: List[SourceChunk] = field(default_factory=list)
    graph_facts: List[GraphFact] = field(default_factory=list)
    structured_result: Optional[Dict[str, Any]] = None
    citations: List[Citation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class GuardrailAssessment:
    allowed: bool = True
    context_relevance_score: float = 1.0
    groundedness_score: float = 1.0
    hallucination_detected: bool = False
    hallucination_reasons: List[str] = field(default_factory=list)
    triggered_input_rail: Optional[str] = None
    triggered_output_rail: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class AnswerResult:
    answer: str
    citations: List[Citation]
    route: str
    confidence: str
