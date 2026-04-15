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
