"""Shared pytest fixtures for the backend test suite."""
from __future__ import annotations

from unittest.mock import patch

import pytest


# The pipeline now builds a per-book dossier as Stage 0 (calls Claude).
# Every pipeline test that isn't explicitly exercising book_research.build_dossier
# should get a stub dossier so no live LLM call fires.
_STUB_DOSSIER = {
    "setting": {"name": "", "era": "", "atmosphere": ""},
    "protagonist_sketch": "",
    "central_conflict": "",
    "themes_tropes": [],
    "visual_motifs": [],
    "tonal_keywords": [],
    "comparable_titles": [],
    "reader_reactions": [],
    "content_hooks": [],
    "signature_images": [],
}


@pytest.fixture(autouse=True)
def _stub_book_dossier_llm():
    """Stub llm.generate_book_dossier so pipelines never hit a live LLM.

    Tests of `book_research.build_dossier` itself can still opt in by
    patching at a different layer (e.g. llm.dispatch) — this fixture only
    stops out the top-level helper.
    """
    with patch(
        "app.services.llm.generate_book_dossier",
        return_value=_STUB_DOSSIER,
    ):
        yield
