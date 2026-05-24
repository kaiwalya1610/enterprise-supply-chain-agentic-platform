from src import chat_cli


def test_main_joins_argv_prompt_and_loads_env(monkeypatch):
    calls = {}

    monkeypatch.setattr(chat_cli.sys, "argv", ["chat_cli", "hello", "there"])
    monkeypatch.setattr(chat_cli, "load_env", lambda: calls.setdefault("load_env", True))
    def fake_answer_once(question):
        calls["question"] = question
        return 0

    monkeypatch.setattr(chat_cli, "_answer_once", fake_answer_once)

    assert chat_cli.main() == 0
    assert calls["load_env"] is True
    assert calls["question"] == "hello there"


def test_main_uses_interactive_mode_when_prompt_is_missing(monkeypatch):
    calls = {}

    monkeypatch.setattr(chat_cli.sys, "argv", ["chat_cli"])
    monkeypatch.setattr(chat_cli, "load_env", lambda: calls.setdefault("load_env", True))
    monkeypatch.setattr(chat_cli, "_interactive", lambda: calls.setdefault("interactive", True) and 0)

    assert chat_cli.main() == 0
    assert calls["load_env"] is True
    assert calls["interactive"] is True
