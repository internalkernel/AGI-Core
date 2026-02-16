"""Configuration via environment variables with sensible defaults."""

import json
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openclaw_dir: Path = Path("/home/botuser/.openclaw")
    gateway_url: str = "http://localhost:18789"
    gateway_ws_url: str = "ws://127.0.0.1:18789"
    gateway_token: str = ""
    host: str = "0.0.0.0"
    port: int = 8765
    log_level: str = "error"
    discovery_interval_seconds: int = 300  # 5 minutes

    # Database
    database_url: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"

    # Webhook
    webhook_api_key: str = ""

    # CORS — extra origins beyond the localhost defaults (comma-separated)
    allowed_origins: str = ""

    # Per-agent gateway tokens (JSON object, e.g. {"devops":"tok1","content-specialist":"tok2"})
    agent_tokens: str = ""

    # Auth
    secret_key: str = ""
    admin_password: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    model_config = {
        "env_prefix": "OPENCLAW_DASH_",
        "env_file": str(Path(__file__).parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    def load_gateway_token(self) -> str:
        """Load gateway token from openclaw.json if not set via env."""
        if self.gateway_token:
            return self.gateway_token
        config_file = self.openclaw_dir / "openclaw.json"
        try:
            if config_file.exists():
                data = json.loads(config_file.read_text())
                self.gateway_token = data.get("gateway", {}).get("auth", {}).get("token", "")
        except Exception:
            pass
        return self.gateway_token


settings = Settings()
settings.load_gateway_token()
