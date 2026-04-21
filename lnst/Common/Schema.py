from pathlib import Path

import lnst


def find_schema(name: str) -> Path:
    for base in lnst.__path__:
        candidate = Path(base) / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Schema '{name}' not found in lnst namespace paths: {list(lnst.__path__)}"
    )
