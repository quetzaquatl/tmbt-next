from __future__ import annotations

import json

import legacy_research_adapter
import research_autopilot_bridge


def main() -> int:
    mods = legacy_research_adapter.activate()
    ra = mods["research_autopilot"]

    request = {}
    try:
        request = json.loads(research_autopilot_bridge.request_path().read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            request = {}
    except Exception:
        request = {}

    profile = str(request.get("profile") or "")
    optimizer_overrides = request.get("optimizer_overrides") or []
    if profile in ra.PROFILES and isinstance(optimizer_overrides, list) and optimizer_overrides:
        # Refined grids are derived only from the previous Development-selected
        # parameters. Trader observations are never injected here.
        ra.PROFILES[profile] = dict(ra.PROFILES[profile])
        ra.PROFILES[profile]["optimizers"] = [
            dict(x) for x in optimizer_overrides if isinstance(x, dict)
        ]

    return int(ra.worker())


if __name__ == "__main__":
    raise SystemExit(main())
