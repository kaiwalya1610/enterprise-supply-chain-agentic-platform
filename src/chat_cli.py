from __future__ import annotations

import sys

from src.config import PROJECT_ROOT
from src.llm_interface import LLMInterfaceError, answer_with_llm, format_cli_result


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _answer_once(question: str) -> int:
    try:
        result = answer_with_llm(question)
    except LLMInterfaceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(format_cli_result(result))
    return 0


def _interactive() -> int:
    print("abc.co supply-chain assistant. Press Ctrl-D or enter a blank line to exit.")
    while True:
        try:
            question = input("> ").strip()
        except EOFError:
            print()
            return 0
        if not question:
            return 0
        status = _answer_once(question)
        if status:
            return status


def main() -> int:
    load_env()
    question = " ".join(sys.argv[1:]).strip()
    if question:
        return _answer_once(question)
    return _interactive()


if __name__ == "__main__":
    raise SystemExit(main())
