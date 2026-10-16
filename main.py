import os
from typing import Any

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow the grader page/browser to call this API from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def coerce(key: str, value: Any) -> Any:
    """Convert raw config values into the required Python types."""
    if value is None:
        return value

    if key in {"port", "workers"}:
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "on"}

    return str(value)


def load_yaml_layer() -> dict:
    """Load config.development.yaml; missing file means no overrides."""
    try:
        with open("config.development.yaml", "r") as f:
            data = yaml.safe_load(f) or {}
        return {k: v for k, v in data.items() if k in DEFAULTS}
    except FileNotFoundError:
        return {}


def load_dotenv_layer() -> dict:
    """Read .env values and map APP_* names to config keys."""
    values = dotenv_values(".env")
    result = {}

    for raw_key, raw_value in values.items():
        if raw_value is None:
            continue

        key = raw_key

        # Special alias: NUM_WORKERS means workers.
        if raw_key == "NUM_WORKERS":
            key = "workers"
        elif raw_key.startswith("APP_"):
            key = raw_key[len("APP_"):].lower()

        if key in DEFAULTS:
            result[key] = raw_value

    return result


def load_os_env_layer() -> dict:
    """Read real OS environment variables beginning with APP_."""
    result = {}

    for raw_key, raw_value in os.environ.items():
        if not raw_key.startswith("APP_"):
            continue

        key = raw_key[len("APP_"):].lower()
        if key in DEFAULTS:
            result[key] = raw_value

    return result


def apply_cli_overrides(config: dict, sets: list[str]) -> dict:
    """Apply ?set=key=value pairs with the highest precedence."""
    for item in sets or []:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        key = key.strip().lower()

        if key in DEFAULTS:
            config[key] = value

    return config


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    # 1. Start with hardcoded defaults.
    config = dict(DEFAULTS)

    # 2. YAML overrides defaults.
    config.update(load_yaml_layer())

    # 3. .env overrides YAML.
    config.update(load_dotenv_layer())

    # 4. OS environment variables override .env.
    config.update(load_os_env_layer())

    # 5. Query parameters override everything.
    config = apply_cli_overrides(config, set)

    # Convert every value to the required type.
    config = {key: coerce(key, value) for key, value in config.items()}

    # Never reveal the real secret.
    config["api_key"] = "****"

    return config