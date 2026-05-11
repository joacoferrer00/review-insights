"""Internationalisation helpers for PDF and dashboard string lookups."""

from pathlib import Path

import yaml

LANG_NAMES: dict[str, str] = {"es": "Spanish", "en": "English"}

_I18N_DIR = Path(__file__).parent


def load_strings(language: str = "es") -> dict[str, str]:
    """Return flat string dict for the given language. Falls back to 'es' for missing keys."""
    lang_file = _I18N_DIR / f"{language}.yaml"
    if not lang_file.exists():
        lang_file = _I18N_DIR / "es.yaml"
    strings = yaml.safe_load(lang_file.read_text(encoding="utf-8"))
    if language != "es":
        es_strings = yaml.safe_load((_I18N_DIR / "es.yaml").read_text(encoding="utf-8"))
        return {**es_strings, **strings}
    return strings
