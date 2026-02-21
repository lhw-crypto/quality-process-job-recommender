from pathlib import Path
import yaml


def load_profile(path: str = "config/profile.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Profile file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
