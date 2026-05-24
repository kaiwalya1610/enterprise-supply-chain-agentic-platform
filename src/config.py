import os
import warnings
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except Exception:
    pass

try:
    from langchain_core._api import LangChainPendingDeprecationWarning

    warnings.filterwarnings(
        "ignore",
        category=LangChainPendingDeprecationWarning,
        message=r".*allowed_objects.*",
    )
except Exception:
    pass


def chroma_telemetry_enabled() -> bool:
    return os.getenv("ANONYMIZED_TELEMETRY", "false").strip().lower() in {"true", "1", "yes", "on"}


def chroma_persistent_client(persist_dir: Path) -> Any:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore

    settings = Settings(anonymized_telemetry=chroma_telemetry_enabled())
    return chromadb.PersistentClient(path=str(persist_dir), settings=settings)

DATASET_DIR = PROJECT_ROOT / "dataset"
KNOWLEDGE_DOCS_DIR = DATASET_DIR / "knowledge_docs"
STRUCTURED_DATA_DIR = DATASET_DIR / "structured"
KNOWLEDGE_MANIFEST_PATH = DATASET_DIR / "knowledge_manifest.json"
CSV_PATH = DATASET_DIR / "inventory_branch_snapshot.csv"
CHROMA_DIR = PROJECT_ROOT / ".chroma" / "abc_ops_docs"
CHROMA_MANIFEST_PATH = CHROMA_DIR / "index_manifest.json"
GRAPH_PATH = PROJECT_ROOT / "knowledge_graph" / "graph.json"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_EMBEDDING_MODEL = "google/gemini-embedding-2-preview"
OPENROUTER_RERANK_MODEL = "cohere/rerank-4-fast"
OPENROUTER_CHAT_MODEL = "deepseek/deepseek-v4-pro"
OPENROUTER_APP_TITLE = "abc-co-rag-assistant"

MARKDOWN_DOCS = [
    DATASET_DIR / "company_backdrop.md",
    DATASET_DIR / "shipment_escalation_sop.md",
    DATASET_DIR / "procurement_approval_policy.md",
    DATASET_DIR / "inventory_kpi_guide.md",
    DATASET_DIR / "customer_communication_playbook.md",
]


def get_markdown_docs() -> list[Path]:
    dynamic_docs = []
    if KNOWLEDGE_DOCS_DIR.exists():
        dynamic_docs = sorted(
            path
            for path in KNOWLEDGE_DOCS_DIR.iterdir()
            if path.suffix.lower() in {".md", ".txt"}
        )
    return [*MARKDOWN_DOCS, *dynamic_docs]

SUPPORTED_DATASET_AREAS = [
    "shipment escalation",
    "procurement approvals",
    "inventory KPIs",
    "customer incident communication",
    "branch inventory CSV analysis",
]


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


GUARDRAIL_MIN_QUALITY_SCORE = _env_float("GUARDRAIL_MIN_QUALITY_SCORE", 0.7)
GUARDRAIL_QUALITY_MAX_RETRIES = _env_int("GUARDRAIL_QUALITY_MAX_RETRIES", 1)
