"""Load webrtcvad even when setuptools has no pkg_resources (setuptools>=82)."""
from __future__ import annotations

import sys
import types
from typing import Any, Optional, Tuple


def _install_pkg_resources_stub() -> None:
    """Minimal stub: webrtcvad only calls pkg_resources.require(...).version."""
    stub = types.ModuleType("pkg_resources")

    class _Dist:
        version = "2.0.10"

    def require(_name: str):  # type: ignore[no-untyped-def]
        return [_Dist()]

    def get_distribution(_name: str):  # type: ignore[no-untyped-def]
        return _Dist()

    stub.require = require  # type: ignore[attr-defined]
    stub.get_distribution = get_distribution  # type: ignore[attr-defined]
    sys.modules["pkg_resources"] = stub


def _ensure_pkg_resources() -> str:
    """
    Ensure pkg_resources is importable.

    Returns:
        "native" | "stub"
    """
    try:
        import pkg_resources  # noqa: F401

        return "native"
    except ImportError:
        pass

    # setuptools>=82 removed pkg_resources entirely — stub is required for webrtcvad
    _install_pkg_resources_stub()
    return "stub"


def load_webrtcvad(mode: int = 1) -> Tuple[Optional[Any], Optional[str]]:
    """
    Returns (Vad instance, error_message).
    error_message is None on success.
    """
    try:
        source = _ensure_pkg_resources()
        # Drop a half-imported broken module from a previous failed attempt
        mod = sys.modules.get("webrtcvad")
        if mod is not None and not hasattr(mod, "Vad"):
            del sys.modules["webrtcvad"]

        import webrtcvad  # type: ignore

        vad = webrtcvad.Vad(max(0, min(int(mode), 3)))
        # Attach meta for debug (optional)
        try:
            vad._pkg_resources_source = source  # type: ignore[attr-defined]
        except Exception:
            pass
        return vad, None
    except Exception as e:
        return None, str(e)
