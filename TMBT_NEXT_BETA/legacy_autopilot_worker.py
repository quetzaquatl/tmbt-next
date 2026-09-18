from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import legacy_research_adapter


def main() -> int:
    mods = legacy_research_adapter.activate()
    ra = mods["research_autopilot"]
    return int(ra.worker())


if __name__ == "__main__":
    raise SystemExit(main())
