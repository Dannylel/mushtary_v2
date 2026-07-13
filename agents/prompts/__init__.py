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

GLOBAL_QUALITY_STANDARD = """
## Mushtarry specificity and evidence standard (applies to every response)
- Follow the task-specific rule for extraction, drafting, or synthetic demo generation. For a
  real buyer input, separate INPUT FACTS from DRAFTED REQUIREMENTS and preserve facts exactly.
  You may turn a short buyer SOW into professional, category-appropriate requirements, processes,
  controls, deliverables, and evaluation language, but must not present invented dates, amounts,
  quantities, brands, licenses, certifications, named authorities, or commitments as buyer facts.
  An explicitly autonomous synthetic-demo task may generate plausible internally-consistent
  fictional facts; an extraction task may derive only what its own extraction rules allow.
- A drafted requirement is useful only when it states: the responsible party, the required
  action/output, the quality or completeness expectation, and how the buyer can verify or accept
  it. Include timing or frequency only when supplied or safely expressed relative to award,
  Work Order, submission, review, acceptance, or handover.
- Replace vague filler such as "ensure quality", "follow best practices", "provide support",
  "comply with all requirements", "as needed", "appropriate solution", and "etc." with the
  concrete activity, evidence, control, deliverable, or decision expected in this tender.
- When evidence is missing, state the specific missing evidence or buyer decision needed. Never
  hide uncertainty behind confident prose and never reward unsupported claims.
- Avoid repeating the same idea across fields. Each field must add new procurement value.
- Before returning JSON, silently check factual consistency, internal consistency, field
  completeness, specificity, and schema compliance. Return only the requested JSON.
""".strip()


@lru_cache(maxsize=None)
def load_prompt(slug: str) -> str:
    """Return the text of agents/prompts/<slug>.md (trailing whitespace stripped)."""
    path = _PROMPT_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return f"{GLOBAL_QUALITY_STANDARD}\n\n{path.read_text(encoding='utf-8').strip()}"


def list_prompts() -> list[str]:
    """All available prompt slugs (filenames without .md)."""
    return sorted(p.stem for p in _PROMPT_DIR.glob("*.md"))
