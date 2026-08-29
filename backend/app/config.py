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
    blockchain_bridge_path: str = "../blockchain/web3_bridge"
    node_feature_count: int = 7
    require_ml_model: bool = False
    demo_allow_mock_ml: bool = True

    scaler_path: str = "../ML/GraphSage-model/scaler.pkl"
    use_scaler_for_inference: bool = False

    ganache_url: str = "http://127.0.0.1:8545"
    contract_address: str = ""
    blockchain_tx_timeout_seconds: int = 5
    # N-05: Signer, Gas, and Outbox configuration
    blockchain_private_key: str = ""
    blockchain_gas_multiplier: float = 1.2
    blockchain_max_gas: int = 600000
    blockchain_retry_interval_seconds: int = 10
    blockchain_max_retries: int = 5
    # N-06: Concurrency, claim lease, pending timeout & chain safety
    blockchain_expected_chain_id: int | None = None
    blockchain_pending_timeout_seconds: int = 180
    blockchain_claim_timeout_seconds: int = 60

    backend_api_token: str = "change-me-for-demo"
    max_analyze_flows: int = 5000
    analyze_rate_limit_per_minute: int = 30

    # Single-operator session auth (Error.md #18/#27). Same "documented
    # insecure default, change it for real use" convention as
    # backend_api_token above — not a required-with-no-default field, so a
    # fresh clone/Docker boot works with zero setup.
    operator_username: str = "admin"
    operator_password: str = "change-me-for-demo"
    session_ttl_hours: int = 8

    enforcement_mode: str = "simulated"  # simulated | ovs
    enforcement_switch: str = "s1"
    mininet_cidr: str = "10.0.0.0/24"
    demo_fallback_flows: bool = False
    
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 50051
    daemon_token: str

    flow_snapshot_retention_hours: int = 24

    # Comma-separated list — see cors_origins_list below (Error.md #28)
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"

    model_config = SettingsConfigDict(
        # Absolute path so the backend always loads backend/.env regardless of
        # the process's working directory — running pytest/uvicorn from the
        # repo root must not pick up the root .env (which has frontend VITE_*
        # keys and is meant for the WSL2/Docker daemon bridge, not the app).
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        protected_namespaces=("settings_",),
        extra="ignore",
    )

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_weights_candidates(self) -> list[Path]:
        configured = Path(self.weights_path)
        if configured.is_absolute():
            return [configured]
        # Resolve strictly relative to the backend directory (where config.py lives)
        backend_dir = Path(__file__).resolve().parent.parent
        return [(backend_dir / configured).resolve()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
