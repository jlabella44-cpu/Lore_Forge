"""Deterministic script quality gate.

Two failure modes — both cheap to check without another LLM round-trip:

1. Banned vocabulary  — the generic-AI-slop words the prompt already forbids.
2. Missing dossier citation  — the rendered script must contain at least
   one item from `dossier.visual_motifs` as a substring (case-insensitive).
   If it doesn't, the model hasn't hung the beat on anything book-specific.

Flag-gated via `settings.quality_gate`. Callers invoke `check_script()`
and, on non-empty result, regenerate the script once with the returned
reasons fed back as a revision note.
"""
from __future__ import annotations

import re


BANNED_VOCAB: tuple[str, ...] = (
    "unputdownable",
    "page-turning",
    "heart-pounding",
    "captivating",
    "a must-read",
    "breathtaking",
    "stunning",
)

_BANNED_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in BANNED_VOCAB) + r")\b",
    re.IGNORECASE,
)


def check_script(script: str, dossier: dict | None) -> list[str]:
    """Return a list of failure reasons. Empty list = pass.

    Reasons are phrased as short imperatives so they can be fed straight
    back to the LLM as a revision note.
    """
    reasons: list[str] = []

    hits = sorted({m.group(0).lower() for m in _BANNED_RE.finditer(script)})
    if hits:
        reasons.append(
            "Remove banned generic vocabulary: " + ", ".join(hits) + "."
        )

    motifs = _visual_motifs(dossier)
    if motifs and not _cites_any(script, motifs):
        sample = ", ".join(motifs[:3])
        reasons.append(
            "Cite at least one concrete visual motif from the dossier "
            f"(e.g. {sample})."
        )

    return reasons


def _visual_motifs(dossier: dict | None) -> list[str]:
    if not dossier:
        return []
    motifs = dossier.get("visual_motifs") or []
    return [m for m in motifs if isinstance(m, str) and m.strip()]


def _cites_any(script: str, motifs: list[str]) -> bool:
    haystack = script.lower()
    return any(m.lower() in haystack for m in motifs)


def feedback_note(reasons: list[str], prior_note: str | None) -> str:
    """Compose a revision note for the retry: the user's original note
    (if any) followed by the gate's reasons."""
    parts: list[str] = []
    if prior_note:
        parts.append(prior_note.strip())
    parts.append("Quality feedback — fix these in the next draft:")
    parts.extend(f"- {r}" for r in reasons)
    return "\n".join(parts)
