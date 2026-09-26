from src.config.settings import Settings


def test_defaults_use_mock_llm_mode() -> None:
    # LLM_MODE=mock is a hard requirement (prompt.md § 52) — the default must
    # never silently require a real API key.
    settings = Settings(_env_file=None)
    assert settings.llm_mode == "mock"


def test_settings_override_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
