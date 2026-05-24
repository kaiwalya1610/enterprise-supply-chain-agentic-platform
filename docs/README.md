# abc.co Hybrid Retrieval Docs

Mermaid-first dry runs for the supply-chain Q&A prototype. Read in order.

| Doc | What it covers |
|-----|----------------|
| [01-high-level-overview.md](./01-high-level-overview.md) | System map, data sources, source eligibility, route labels |
| [02-low-level-dry-run.md](./02-low-level-dry-run.md) | Parallel retrieval traces and legacy route traces with dummy values |
| [03-bootstrap-pipeline.md](./03-bootstrap-pipeline.md) | Offline build: graph export, Chroma index, eval loop |
| [04-guardrails-and-grounding.md](./04-guardrails-and-grounding.md) | Input/output guardrails, grounding scores, hallucination detection |
| [05-future-scope.md](./05-future-scope.md) | Future scope: UI uploads, access control, caching, eval data, fine-tuning |

**Entry points**

- `answer_with_llm()` / `answer_with_llm_events()` in `src/llm_interface.py` for chat
- `retrieve_parallel_context(question)` in `src/retriever.py` for the chat retrieval path
- `answer_question(question)` in `src/rag_answerer.py` for the legacy deterministic formatter
- `python3 eval/evaluate.py` for the 25-question regression suite
- `python3 -m knowledge_graph.build_graph` to refresh `knowledge_graph/graph.json`
