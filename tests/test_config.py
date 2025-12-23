from src.core.config import settings

def test_config_defaults():
    assert settings.ENV in {"dev", "test", "prod"}
    assert isinstance(settings.HEADLESS, bool)
    assert settings.NAV_TIMEOUT_MS > 0
