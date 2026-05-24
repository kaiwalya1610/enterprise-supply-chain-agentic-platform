# High-Level Overview

Hybrid retrieval for abc.co ops questions. One question in, one grounded answer out.

The chat path uses parallel retrieval plus LLM synthesis. The legacy deterministic path still exists for eval and `answer_question()`.

## TL;DR

- **Source eligibility** picks candidate retrievers: docs, graph, and/or CSV.
- **Parallel retrieval** fetches eligible evidence, reranks docs, and merges one bundle.
- **Same LLM call** classifies which source families matter and writes the final answer.
- **Three data planes**: Markdown SOPs, `inventory_branch_snapshot.csv`, and `knowledge_graph/graph.json`.
- **Semantic search** (OpenRouter embed + Chroma + rerank) with lexical fallback when API keys are missing.

## System map

### Chat path (FastAPI / LangGraph)

```mermaid
flowchart TD
    Q[/User question/] --> G[Input guardrails]
    G --> E[eligible_sources_for_question]
    E --> RC[retriever.retrieve_parallel_context]
    RC --> B[rag_answerer.answer_from_bundle]
    B --> LLM[llm_interface synthesize]
    LLM --> OUT[\LLMInterfaceResult\]

    RC --> DOC[(Markdown chunks)]
    RC --> KG[(graph.json)]
    RC --> CSV[(inventory CSV)]
```

### Legacy deterministic path

```mermaid
flowchart TD
    Q2[/User question/] --> R[question_router.route_question]
    R --> RC2[retriever.retrieve_context]
    RC2 --> A[rag_answerer.answer_from_bundle]
    A --> OUT2[\AnswerResult\]
```

## Data sources

```mermaid
flowchart TD
    DS[dataset/] --> MD[5 policy SOPs .md]
    DS --> CSV[inventory_branch_snapshot.csv]
    DS --> EVAL[eval_questions.json]

    MD --> ING[ingest_docs.parse_markdown_file]
    ING --> CHUNKS[SourceChunk list]

    CSV --> KGCSV[kg_from_csv.add_csv_graph]
    MD --> KGDOCS[kg_from_docs.add_document_graph]
    KGCSV --> BUILD[build_graph.write_graph]
    KGDOCS --> BUILD
    BUILD --> GJ[graph.json]

    CHUNKS --> CHROMA[DocumentRetriever Chroma index]
```

## Source eligibility

Cheap prefilter only. It does not choose the final route.

```mermaid
flowchart TD
    START([question str]) --> G{guardrails.detect_guardrail_route}
    G -->|injection pattern| GR[guardrail early exit]
    G -->|unsupported topic| UNS[unsupported early exit]
    G -->|none| M{missing inputs?}
    M -->|yes| AMB[ambiguous early exit]
    M -->|no| E{eligible_sources_for_question}
    E -->|docs terms| D[docs retriever]
    E -->|graph terms or SKU| G2[graph retriever]
    E -->|CSV terms + inventory context| S[structured_csv retriever]
    E -->|none| UNS2[unsupported]
    D --> P[ThreadPoolExecutor parallel fetch]
    G2 --> P
    S --> P
    P --> R[_route_from_evidence metadata label]
```

## Route labels

Route labels are derived from retrieved evidence, not from a pre-retrieval router in the chat path.

| Label | Meaning | Typical evidence |
|-------|---------|------------------|
| `rag_policy` | docs only | doc chunks + citations |
| `graph_lookup` | graph only | graph facts |
| `structured_data` | CSV only | pandas result dict |
| `hybrid` | multiple families | graph + docs and/or CSV |
| `ambiguous` | missing inputs | clarification prompt |
| `guardrail` | injection / artifact | refusal |
| `unsupported` | no eligible or empty evidence | out-of-scope message |

## Public API surface

```mermaid
flowchart LR
    INIT[src/__init__.py] --> AQ[answer_question legacy]
    INIT --> RC[retrieve_context legacy]

    API[src/api.py] --> LLM[answer_with_llm]
    LLM --> RPC[retrieve_parallel_context]
    LLM --> AFB[answer_from_bundle]

    RPC --> DR[DocumentRetriever]
    RPC --> GQ[graph_queries]
    RPC --> SD[answer_structured_question]
    RC --> RQ[route_question legacy]
```

> **Legend**: Cylinders = persisted data. Diamonds = guardrail or eligibility checks. Rounded = I/O boundaries.
