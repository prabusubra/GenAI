import os


def test_application_loads_dotenv_without_overriding_shell_values(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=gemini\n")
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    from dotenv import load_dotenv

    load_dotenv(env_file)

    assert os.environ["LLM_PROVIDER"] == "groq"
