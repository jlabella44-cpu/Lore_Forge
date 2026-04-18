"""profiles router — CRUD + YAML round-trip."""
from __future__ import annotations

import yaml


def test_list_profiles_returns_seeded_books(client):
    res = client.get("/profiles")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["slug"] == "books"
    assert data[0]["active"] is True


def test_get_active_returns_books(client):
    res = client.get("/profiles/active")
    assert res.status_code == 200
    assert res.json()["slug"] == "books"


def test_get_active_404_when_nothing_active(client):
    # Flip books inactive directly via the ORM.
    from app.db import SessionLocal
    from app.models import Profile

    db = SessionLocal()
    try:
        db.query(Profile).update({Profile.active: False})
        db.commit()
    finally:
        db.close()

    assert client.get("/profiles/active").status_code == 404


def test_get_one_404s_on_unknown_slug(client):
    assert client.get("/profiles/nope").status_code == 404


def test_create_profile_then_activate(client):
    body = {
        "slug": "films",
        "name": "Films",
        "entity_label": "Film",
        "description": "Movie trailer shorts.",
        "taxonomy": ["drama", "scifi"],
        "render_tones": {"scifi": "hype"},
    }
    res = client.post("/profiles", json=body)
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["slug"] == "films"
    assert created["active"] is False
    assert created["taxonomy"] == ["drama", "scifi"]

    # Activate — books goes inactive, films goes active.
    res = client.post("/profiles/films/activate")
    assert res.status_code == 200
    assert res.json()["active"] is True

    active = client.get("/profiles/active").json()
    assert active["slug"] == "films"


def test_create_profile_rejects_duplicate_slug(client):
    res = client.post(
        "/profiles",
        json={"slug": "books", "name": "Dup", "entity_label": "Dup"},
    )
    assert res.status_code == 409


def test_patch_profile_partial_update(client):
    res = client.patch(
        "/profiles/books",
        json={"description": "A test description."},
    )
    assert res.status_code == 200
    assert res.json()["description"] == "A test description."
    # Untouched fields stay.
    assert res.json()["entity_label"] == "Book"


def test_delete_refuses_active_profile(client):
    res = client.delete("/profiles/books")
    assert res.status_code == 409
    assert "active" in res.json()["detail"].lower()


def test_delete_refuses_profile_with_content_items(client):
    # Create films, attach an item, flip films active so books can
    # delete — but attach the item to books before the flip.
    from app.db import SessionLocal
    from app.models import ContentItem, Profile

    client.post(
        "/profiles",
        json={"slug": "films", "name": "Films", "entity_label": "Film"},
    )
    db = SessionLocal()
    try:
        books = db.query(Profile).filter(Profile.slug == "books").one()
        db.add(ContentItem(profile_id=books.id, title="X", subtitle="Y"))
        db.commit()
    finally:
        db.close()

    # Activate films so we can even attempt to delete books.
    client.post("/profiles/films/activate")
    res = client.delete("/profiles/books")
    assert res.status_code == 409
    assert "ContentItem" in res.json()["detail"]


def test_delete_removes_unused_inactive_profile(client):
    client.post(
        "/profiles",
        json={"slug": "films", "name": "Films", "entity_label": "Film"},
    )
    res = client.delete("/profiles/films")
    assert res.status_code == 200
    assert client.get("/profiles/films").status_code == 404


# ---------------------------------------------------------------------------
# YAML round-trip
# ---------------------------------------------------------------------------


def test_export_yaml_round_trips_through_import(client):
    # Dump books.
    export = client.get("/profiles/books/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/x-yaml")

    parsed = yaml.safe_load(export.content)
    assert parsed["slug"] == "books"
    # Export omits volatile fields.
    assert "active" not in parsed
    assert "id" not in parsed
    assert "created_at" not in parsed

    # Tweak the slug + re-import.
    parsed["slug"] = "books-copy"
    parsed["name"] = "Books Copy"
    new_yaml = yaml.safe_dump(parsed, sort_keys=False)
    res = client.post(
        "/profiles/import",
        content=new_yaml,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["slug"] == "books-copy"
    assert res.json()["active"] is False  # imports are never active

    # Taxonomy + cta_fields survived.
    copied = client.get("/profiles/books-copy").json()
    original = client.get("/profiles/books").json()
    assert copied["taxonomy"] == original["taxonomy"]
    assert copied["cta_fields"] == original["cta_fields"]


def test_import_requires_overwrite_on_existing_slug(client):
    payload = yaml.safe_dump(
        {"slug": "books", "name": "hand-edit", "entity_label": "Book"}
    )
    res = client.post(
        "/profiles/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 409
    assert "overwrite" in res.json()["detail"]


def test_import_overwrite_true_replaces_existing(client):
    payload = yaml.safe_dump(
        {
            "slug": "books",
            "name": "Books (edited)",
            "entity_label": "Book",
            "description": "After reimport",
        }
    )
    res = client.post(
        "/profiles/import?overwrite=true",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Books (edited)"
    assert res.json()["description"] == "After reimport"


def test_import_rejects_unknown_yaml_keys(client):
    payload = yaml.safe_dump(
        {"slug": "x", "name": "x", "entity_label": "x", "zzz_typo": 1}
    )
    res = client.post(
        "/profiles/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 400
    assert "zzz_typo" in res.json()["detail"]


def test_import_rejects_missing_required_keys(client):
    payload = yaml.safe_dump({"slug": "x"})
    res = client.post(
        "/profiles/import",
        content=payload,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 400
    assert "entity_label" in res.json()["detail"]


def test_import_bundle_loads_all_example_profiles(client):
    res = client.post("/profiles/import-bundle")
    assert res.status_code == 200, res.text
    body = res.json()
    # Every shipped example imports cleanly.
    assert set(body["imported"]) == {"movies", "recipes", "news"}
    assert body["skipped"] == []

    # Each one is retrievable via the single-profile endpoint.
    for slug in ("movies", "recipes", "news"):
        assert client.get(f"/profiles/{slug}").status_code == 200


def test_import_bundle_skips_existing_without_overwrite(client):
    first = client.post("/profiles/import-bundle").json()
    assert first["imported"]

    second = client.post("/profiles/import-bundle").json()
    # Everything that was imported the first time is now skipped with
    # reason="exists".
    assert second["imported"] == []
    reasons = {s.get("reason") for s in second["skipped"]}
    assert reasons == {"exists"}


def test_import_bundle_overwrite_replaces_existing(client):
    client.post("/profiles/import-bundle")
    # Tweak one of them out-of-band so we can prove overwrite resets it.
    client.patch("/profiles/movies", json={"description": "hand-edited"})
    overwritten = client.post("/profiles/import-bundle?overwrite=true").json()
    assert "movies" in overwritten["imported"]
    assert (
        client.get("/profiles/movies").json()["description"]
        != "hand-edited"
    )


def test_import_rejects_bad_yaml(client):
    res = client.post(
        "/profiles/import",
        content="this: [is not [valid yaml",
        headers={"Content-Type": "application/x-yaml"},
    )
    assert res.status_code == 400
