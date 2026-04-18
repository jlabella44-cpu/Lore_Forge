"""GET /books, GET /books/{id}, PATCH /books/{id}."""
from unittest.mock import patch

NYT_ONE = [
    {
        "title": "The Ghost Orchid",
        "author": "David Baldacci",
        "isbn": "9781538765388",
        "description": "A mystery.",
        "cover_url": None,
        "source_rank": 1,
    }
]


def _seed_one(client, genre=("thriller", 0.85)):
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=genre),
    ):
        client.post("/discover/run")
    return client.get("/books").json()[0]["id"]


def test_list_books_empty(client):
    res = client.get("/books")
    assert res.status_code == 200
    assert res.json() == []


def test_list_books_returns_effective_genre(client):
    book_id = _seed_one(client)

    # Override — effective genre should flip to fantasy, source should be "override"
    client.patch(f"/books/{book_id}", json={"genre_override": "fantasy"})
    book = client.get("/books").json()[0]
    assert book["genre"] == "fantasy"
    assert book["genre_source"] == "override"

    # Clear override — back to auto-classified thriller
    client.patch(f"/books/{book_id}", json={"genre_override": None})
    book = client.get("/books").json()[0]
    assert book["genre"] == "thriller"
    assert book["genre_source"] == "auto"


def test_get_book_detail(client):
    book_id = _seed_one(client)
    res = client.get(f"/books/{book_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == book_id
    assert detail["title"] == "The Ghost Orchid"
    assert detail["isbn"] == "9781538765388"
    assert detail["packages"] == []


def test_book_404s(client):
    assert client.get("/books/99999").status_code == 404
    assert client.patch("/books/99999", json={}).status_code == 404
    assert client.post("/books/99999/skip").status_code == 404
    assert client.post("/books/99999/unskip").status_code == 404


def test_skip_hides_book_from_default_queue(client):
    book_id = _seed_one(client)
    assert len(client.get("/books").json()) == 1

    assert client.post(f"/books/{book_id}/skip").status_code == 200

    # Default list omits skipped books
    assert client.get("/books").json() == []

    # But include_skipped=true surfaces them
    listed = client.get("/books?include_skipped=true").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "skipped"


def test_unskip_restores_visibility(client):
    book_id = _seed_one(client)
    client.post(f"/books/{book_id}/skip")
    assert client.get("/books").json() == []

    client.post(f"/books/{book_id}/unskip")
    listed = client.get("/books").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "discovered"


def test_patch_can_set_status_directly(client):
    """PATCH /books/{id} with {"status": "published"} is a sharp edge for
    admin/debug; covers the case where someone wants to correct a wedged
    book without hitting the typed skip/unskip endpoints."""
    book_id = _seed_one(client)
    assert client.patch(f"/books/{book_id}", json={"status": "published"}).status_code == 200
    assert client.get(f"/books/{book_id}").json()["status"] == "published"


# --- dossier editing -------------------------------------------------------


_SAMPLE_DOSSIER = {
    "setting": {"name": "drowned city", "era": "", "atmosphere": ""},
    "visual_motifs": ["coral lattice"],
    "themes_tropes": ["climate grief"],
}


def test_book_detail_exposes_dossier(client):
    book_id = _seed_one(client)
    assert client.get(f"/books/{book_id}").json()["dossier"] is None

    client.patch(f"/books/{book_id}", json={"dossier": _SAMPLE_DOSSIER})
    assert client.get(f"/books/{book_id}").json()["dossier"] == _SAMPLE_DOSSIER


def test_patch_dossier_replaces_wholesale(client):
    """PATCH replaces the dossier — no partial merge. Caller owns the shape."""
    book_id = _seed_one(client)
    client.patch(f"/books/{book_id}", json={"dossier": _SAMPLE_DOSSIER})

    new_dossier = {"setting": {"name": "bright garden"}, "visual_motifs": []}
    client.patch(f"/books/{book_id}", json={"dossier": new_dossier})

    assert client.get(f"/books/{book_id}").json()["dossier"] == new_dossier


def test_patch_dossier_null_clears(client):
    """Clearing the dossier primes the next /generate to rebuild via LLM."""
    book_id = _seed_one(client)
    client.patch(f"/books/{book_id}", json={"dossier": _SAMPLE_DOSSIER})

    client.patch(f"/books/{book_id}", json={"dossier": None})
    assert client.get(f"/books/{book_id}").json()["dossier"] is None


def test_patch_dossier_rejects_non_object(client):
    book_id = _seed_one(client)
    res = client.patch(f"/books/{book_id}", json={"dossier": "not a dict"})
    assert res.status_code == 400
    assert "dossier" in res.json()["detail"].lower()


def test_patch_dossier_leaves_other_fields_untouched(client):
    """PATCH with only a dossier key must not disturb genre_override/status."""
    book_id = _seed_one(client)
    client.patch(f"/books/{book_id}", json={"genre_override": "fantasy"})

    client.patch(f"/books/{book_id}", json={"dossier": _SAMPLE_DOSSIER})

    detail = client.get(f"/books/{book_id}").json()
    assert detail["dossier"] == _SAMPLE_DOSSIER
    assert detail["genre_override"] == "fantasy"
