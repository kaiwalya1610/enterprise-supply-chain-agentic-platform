# Bootstrap Pipeline

Offline steps that populate indexes before any question hits the runtime path.

---

## Graph build

**Assumptions:** fresh clone, CSV has 60 SKU rows, 5 markdown docs present

```mermaid
graph TD
    CLI(["python3 -m knowledge_graph.build_graph"]) --> BG["build_graph()"]
    BG --> NX["nx.MultiDiGraph empty"]
    NX --> DOC["add_document_graph | teams roles thresholds KPIs delays"]
    DOC --> CSV["add_csv_graph | 60 SKUs x branches categories suppliers"]
    CSV --> EXP["_export | nodes sorted edges sorted"]
    EXP --> WJ["write_graph -> knowledge_graph/graph.json"]
    WJ --> DONE(["stdout | Wrote graph.json with N nodes M edges"])

    style CLI fill:#d1fae5,stroke:#047857,stroke-width:2px,color:#064e3b
    style DONE fill:#d1fae5,stroke:#047857,stroke-width:2px,color:#064e3b
    style WJ fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e
```

### Document graph nodes (from `kg_from_docs.py`)

```mermaid
graph TD
    AD["_add_documents | 5 Document nodes"] --> AT["_add_teams_and_roles | Team Role nodes"]
    AT --> AP["_add_procurement | ApprovalThreshold + REQUIRES_APPROVAL_FROM"]
    AP --> ADE["_add_delay_escalation | Severity 0-4 + ESCALATES_TO"]
    ADE --> ACC["_add_customer_communication | playbook edges"]
    ACC --> AK["_add_kpis | KPI nodes + CALCULATED_FROM columns"]

    style AD fill:#f1f5f9,stroke:#64748b,color:#0f172a
```

### CSV graph edges (per row)

**Dummy row:** sku=`ELC-TV-55-4K`, branch=`Mumbai`, category=`Electronics`, supplier=`TechVision`

```mermaid
graph TD
    ROW["CSV row ELC-TV-55-4K"] --> N1["add_node SKU with row attrs"]
    ROW --> N2["add_node Branch Mumbai"]
    ROW --> N3["add_node Category Electronics"]
    ROW --> N4["add_node Supplier TechVision"]
    N1 --> E1["ELC-TV-55-4K STOCKED_AT Mumbai"]
    N1 --> E2["ELC-TV-55-4K BELONGS_TO_CATEGORY Electronics"]
    N1 --> E3["ELC-TV-55-4K SUPPLIED_BY TechVision"]
    N2 --> E4["Mumbai HAS_SKU ELC-TV-55-4K"]

    style ROW fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e
```

---

## Chroma index build (lazy on first query)

**Assumptions:** first call to `DocumentRetriever()`, manifest missing

```mermaid
graph TD
    FIRST["first DocumentRetriever()"] --> CHUNKS["load_markdown_chunks | ~40-60 chunks"]
    CHUNKS --> OR["OpenRouterClient | OPENROUTER_API_KEY required"]
    OR --> CHROMA["chromadb get_or_create_collection abc_ops_docs"]
    CHROMA --> ENSURE["_ensure_index | manifest_matches=false"]
    ENSURE --> BATCH["embed_texts all chunk texts search_document"]
    BATCH --> ADD["collection.add with explicit embeddings"]
    ADD --> MAN["write index_manifest.json"]
    MAN --> READY["semantic_available=true"]

    style OR fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e
    style MAN fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e
```

**Manifest invalidation triggers rebuild when any of these change:**

- chunk count
- content SHA256 hash
- embedding model name
- collection count mismatch

---

## Runtime lazy graph load

**Assumptions:** `graph.json` deleted, first question arrives

```mermaid
graph TD
    L1["graph_queries.load_graph @lru_cache"] --> L2{"GRAPH_PATH exists?"}
    L2 -->|yes| L3["json.loads graph.json"]
    L2 -->|no| L4["build_graph() in memory"]
    L4 --> L3
    L3 --> L5["cached for process lifetime"]

    style L2 fill:#fef9c3,stroke:#ca8a04,color:#713f12
```

---

## Full cold-start sequence

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant BG as build_graph
    participant GJ as graph.json
    participant Chat as answer_with_llm
    participant RPC as retrieve_parallel_context
    participant DR as DocumentRetriever
    participant OR as OpenRouter API
    participant CH as Chroma

    Dev->>BG: python3 -m knowledge_graph.build_graph
    BG->>GJ: write nodes + edges
    Dev->>Chat: answer_with_llm(q)
    Chat->>RPC: eligible sources + parallel fetch
    RPC->>DR: DocumentRetriever()
    DR->>OR: embed_texts chunks
    OR-->>DR: N x 768 vectors
    DR->>CH: collection.add
    RPC->>OR: embed query + rerank
    OR-->>Chat: top chunks + graph + CSV bundle
    Chat->>GJ: load_graph via graph_queries
    Chat-->>Dev: LLMInterfaceResult
```

---

## Install and verify

```mermaid
graph TD
    I1["pip install -r requirements.txt"] --> I2["export OPENROUTER_API_KEY"]
    I2 --> I3["python3 -m knowledge_graph.build_graph"]
    I3 --> I4["python3 -m pytest"]
    I4 --> I5["python3 eval/evaluate.py"]
    I5 --> I6(["expected passed=25 total=25"])

    style I6 fill:#d1fae5,stroke:#047857,stroke-width:2px,color:#064e3b
```

> **Legend**: Sequence diagram = cross-service I/O. Graph TD = in-process call order.
