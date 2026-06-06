# [WSL2]
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    sqlite_path: str = "./graphsentinel.db"
    threat_threshold: float = 0.75
    poll_interval_seconds: int = 5

    weights_path: str = "../ML/GraphSage-model/graphsage_weights.pt"
    model_source_path: str = "../ml/src"
    node_feature_count: int = 7
    require_ml_model: bool = False
    demo_allow_mock_ml: bool = True

    scaler_path: str = "../ML/GraphSage-model/scaler.pkl"
    use_scaler_for_inference: bool = False

    ganache_url: str = "http://127.0.0.1:8545"
    contract_address: str = ""
    blockchain_tx_timeout_seconds: int = 5

    backend_api_token: str = "change-me-for-demo"
    max_analyze_flows: int = 5000
    analyze_rate_limit_per_minute: int = 30

    enforcement_mode: str = "simulated"  # simulated | ovs
    enforcement_switch: str = "s1"
    enforcement_agent_socket: str = "/tmp/graphsentinel-enforcer.sock"
    mininet_cidr: str = "10.0.0.0/24"
    demo_fallback_flows: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        protected_namespaces=("settings_",),
    )

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"

    @property
    def resolved_weights_candidates(self) -> list[Path]:
        root = Path(__file__).resolve().parents[2]
        configured = Path(self.weights_path)
        candidates = [configured]
        if not configured.is_absolute():
            candidates.append((root / self.weights_path).resolve())
        candidates.extend(
            [
                (root / "../ML/GraphSage-model/graphsage_weights.pt").resolve(),
                (root / "../ml/models/graphsage_weights.pt").resolve(),
                (root / "ML/GraphSage-model/graphsage_weights.pt").resolve(),
                (root / "ml/models/graphsage_weights.pt").resolve(),
            ]
        )
        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return unique


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
