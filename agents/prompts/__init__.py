"""
Prompt store — every model prompt lives in its own file under this folder.

Prompts are kept OUT of the Python code: each system/instruction prompt is a standalone
`.md` file here, loaded at runtime with `load_prompt("<slug>")`. This keeps prompt text
editable without touching code, diff-friendly, and one-prompt-per-file.

Naming: `<area>_<role>.md` (e.g. `vendor_validation_system.md`, `drafting_scope_system.md`).
"""
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_prompt(slug: str) -> str:
    """Return the text of agents/prompts/<slug>.md (trailing whitespace stripped)."""
    path = _PROMPT_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def list_prompts() -> list[str]:
    """All available prompt slugs (filenames without .md)."""
    return sorted(p.stem for p in _PROMPT_DIR.glob("*.md"))
