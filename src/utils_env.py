from __future__ import annotations
import os

def get_env_str(key: str, default: str) -> str:
    v = os.getenv(key)
    return default if v is None or v.strip() == "" else v.strip()

def get_env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v, 0)
    except ValueError:
        return default
