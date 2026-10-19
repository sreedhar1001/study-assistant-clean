"""Application configuration loading."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILES = (ROOT / ".env.example", ROOT / ".env")


def load_config() -> dict[str, str]:
    """Load local configuration files, with process environment taking precedence."""
    values: dict[str, str] = {}
    for config_file in CONFIG_FILES:
        if not config_file.is_file():
            continue
        for raw_line in config_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if name.startswith("export "):
                name = name[7:].strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if not value or value.casefold().startswith(("your-", "your_", "replace-", "replace_", "<")):
                continue
            values[name] = value

    if os.environ.get("TAVILY_API_KEY"):
        values["TAVILY_API_KEY"] = os.environ["TAVILY_API_KEY"]
    for name in ("GROQ_API_KEY", "GROQ_MODEL"):
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def configured_providers() -> list[str]:
    return ["tavily"] if load_config().get("TAVILY_API_KEY") else []
