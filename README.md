# enterprise-supply-chain-agentic-platform

Hybrid retrieval prototype for the synthetic abc.co supply-chain operations dataset.

## What is implemented

- Section-aware Markdown ingestion for internal policies and SOPs.
- OpenRouter semantic retriever using `google/gemini-embedding-2-preview`, Chroma, and `cohere/rerank-4-fast`.
- Deterministic lexical fallback when OpenRouter credentials or Chroma are unavailable.
- Pandas-backed structured inventory analysis with a CSV fallback for minimal environments.
- NetworkX-compatible lightweight knowledge graph exported to `knowledge_graph/graph.json`.
- Question router for RAG, graph lookup, structured data, hybrid, ambiguous, unsupported, and guardrail paths.
- Guardrails for unsupported topics and prompt-injection test artifacts.
- Evaluation runner for all 25 dataset questions.

## Install

```bash
python3 -m pip install -r requirements.txt
```

The code can still run basic smoke checks without optional packages, but installing dependencies enables the intended Chroma, Pandas, NetworkX, and pytest stack.

## Configure OpenRouter retrieval

```bash
export OPENROUTER_API_KEY="sk-or-..."
export OPENROUTER_EMBEDDING_MODEL="google/gemini-embedding-2-preview"
export OPENROUTER_RERANK_MODEL="cohere/rerank-4-fast"
```

When `OPENROUTER_API_KEY` is set, document retrieval works as:

1. Embed section-aware Markdown chunks with OpenRouter.
2. Store explicit embeddings in Chroma under `.chroma/abc_ops_docs`.
3. Embed the user query with the same embedding model.
4. Run Chroma similarity search for candidates.
5. Rerank candidates through OpenRouter.

The local Chroma index has an `index_manifest.json` sidecar and rebuilds when chunk content or the embedding model changes.

## Build the graph

```bash
python3 -m knowledge_graph.build_graph
```

This writes `knowledge_graph/graph.json`.

## Visualize the graph

Generate interactive HTML subgraph views with PyVis:

```bash
python3 -m knowledge_graph.visualize_graph --view policy_overview --open
python3 -m knowledge_graph.visualize_graph --view procurement
python3 -m knowledge_graph.visualize_graph --view sku --sku ELEC-WEBCAM-03
python3 -m knowledge_graph.visualize_graph --view branch --branch Mumbai
python3 -m knowledge_graph.visualize_graph --stats
```

Output HTML files are written to `knowledge_graph/viz/`.

## Use the retrieval service

```python
from src import answer_question, retrieve_context, route_question

question = "Who approves procurement requests above ₹5,00,000 at abc.co?"
print(route_question(question))
print(answer_question(question).answer)
```

## Run evaluation

```bash
python3 eval/evaluate.py
```

Expected result:

```json
{
  "passed": 25,
  "total": 25
}
```

## Run tests

```bash
python3 -m pytest
```
