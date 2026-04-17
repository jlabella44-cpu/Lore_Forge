"""Per-genre visual style presets for scene-prompt generation.

Each preset is a small bundle of defaults — palette, lens, lighting,
composition — that the scene-prompt stage treats as a baseline when the
dossier doesn't specify something more concrete. Dossier wins on conflict
(a book set in a bright coral reef overrides horror's charcoal palette).

Adding a new genre: append an entry below and mirror the value in
`classify_genre`'s allowed enum in `llm.py`.
"""
from __future__ import annotations

from typing import TypedDict


class GenrePreset(TypedDict):
    palette: list[str]
    lens: str
    lighting: str
    composition: str


GENRE_PRESETS: dict[str, GenrePreset] = {
    "fantasy": {
        "palette": ["forest green", "gold leaf", "dusk purple", "candleflame amber"],
        "lens": "anamorphic wide or 35mm",
        "lighting": "golden-hour side light with practical candle/lantern sources",
        "composition": "low-angle heroic, deep focus",
    },
    "thriller": {
        "palette": ["bruise blue", "sodium-vapor orange", "ink black", "cigarette smoke"],
        "lens": "35mm, shallow depth of field",
        "lighting": "harsh key with negative fill, single practical source",
        "composition": "Dutch angle, claustrophobic framing, off-center subject",
    },
    "scifi": {
        "palette": ["chrome white", "cyan bloom", "magenta edge", "deep-space black"],
        "lens": "25mm or 32mm, minimal distortion",
        "lighting": "hard rim light bounced off colored surfaces",
        "composition": "symmetrical wide, architectural scale",
    },
    "romance": {
        "palette": ["blush pink", "cream", "soft sage", "terracotta"],
        "lens": "50mm or 85mm, f/1.8 bokeh",
        "lighting": "backlit golden hour with warm diffused fill",
        "composition": "tight two-shot or medium close-up, soft background",
    },
    "horror": {
        "palette": ["charcoal", "blood crimson", "sick green", "bone white"],
        "lens": "24mm wide for unease or 85mm for isolation",
        "lighting": "underlit faces, high-contrast shadow play",
        "composition": "negative space overhead, subject pushed to frame edge",
    },
    "historical_fiction": {
        "palette": ["sepia", "aged paper ivory", "iron grey", "velvet crimson"],
        "lens": "50mm natural look",
        "lighting": "window light, candle practicals, soft overcast",
        "composition": "classical rule-of-thirds, period-appropriate framing",
    },
}


def get(genre: str | None) -> GenrePreset | None:
    """Return the preset for `genre`, or None if unknown / 'other' / falsy."""
    if not genre:
        return None
    return GENRE_PRESETS.get(genre.lower())


def preset_block(genre: str | None) -> str:
    """Format a preset as a text block for inclusion in a user message.

    Empty string when the genre has no preset, so callers can append
    unconditionally without worrying about spurious blank sections.
    """
    preset = get(genre)
    if preset is None:
        return ""
    return (
        "\n\nVisual preset (baseline — dossier wins on conflict):\n"
        f"  palette: {', '.join(preset['palette'])}\n"
        f"  lens: {preset['lens']}\n"
        f"  lighting: {preset['lighting']}\n"
        f"  composition: {preset['composition']}"
    )
