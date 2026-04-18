"""cta_links JSON column on ContentPackage + Books-era @property shims."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ContentItem, ContentPackage, Profile


REPO_ROOT = Path(__file__).resolve().parents[2]


def _fresh_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cta.sqlite'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Profile(
            slug="books",
            name="Books",
            entity_label="Book",
            active=True,
            sources_config=[],
            prompts={},
            taxonomy=[],
            cta_fields=[],
            render_tones={},
        )
    )
    session.commit()
    item = ContentItem(profile_id=1, title="T", subtitle="A")
    session.add(item)
    session.flush()
    return session, item


def test_affiliate_amazon_setter_writes_to_cta_links(tmp_path):
    session, item = _fresh_session(tmp_path)
    pkg = ContentPackage(content_item_id=item.id, revision_number=1)
    pkg.affiliate_amazon = "https://amazon.com/dp/X"
    assert pkg.cta_links == {"amazon_url": "https://amazon.com/dp/X"}
    assert pkg.affiliate_amazon == "https://amazon.com/dp/X"
    assert pkg.affiliate_bookshop is None


def test_both_affiliate_setters_coexist(tmp_path):
    session, item = _fresh_session(tmp_path)
    pkg = ContentPackage(
        content_item_id=item.id,
        revision_number=1,
        affiliate_amazon="https://amazon.com/dp/X",
        affiliate_bookshop="https://bookshop.org/a/loreforge/X",
    )
    assert pkg.cta_links == {
        "amazon_url": "https://amazon.com/dp/X",
        "bookshop_url": "https://bookshop.org/a/loreforge/X",
    }


def test_setting_none_removes_key(tmp_path):
    session, item = _fresh_session(tmp_path)
    pkg = ContentPackage(
        content_item_id=item.id,
        revision_number=1,
        affiliate_amazon="https://amazon.com/dp/X",
        affiliate_bookshop="https://bookshop.org/X",
    )
    pkg.affiliate_amazon = None
    assert pkg.cta_links == {"bookshop_url": "https://bookshop.org/X"}
    pkg.affiliate_bookshop = None
    # Empty → None so nullable column stays clean.
    assert pkg.cta_links is None


def test_cta_links_round_trips_through_commit(tmp_path):
    session, item = _fresh_session(tmp_path)
    pkg = ContentPackage(
        content_item_id=item.id,
        revision_number=1,
        affiliate_amazon="https://amazon.com/dp/Y",
    )
    session.add(pkg)
    session.commit()
    session.expire_all()

    reloaded = session.get(ContentPackage, pkg.id)
    assert reloaded.cta_links == {"amazon_url": "https://amazon.com/dp/Y"}
    assert reloaded.affiliate_amazon == "https://amazon.com/dp/Y"


def test_migration_0011_moves_legacy_columns_into_cta_links(tmp_path):
    """Drive alembic from 0001 → head, seed pre-0011 rows with affiliate
    columns, then confirm 0011 repacks them into cta_links without loss.
    """
    db_file = tmp_path / "mig.sqlite"
    url = f"sqlite:///{db_file}"

    env = os.environ.copy()
    env["DATABASE_URL"] = url

    # Step 1: upgrade to the revision BEFORE 0011, seed legacy data.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0010_content_items"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO content_items "
                "(profile_id, title, subtitle, status, score, discovered_at) "
                "VALUES (1, 'Old', 'Author', 'review', 1.0, "
                "CURRENT_TIMESTAMP)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content_packages "
                "(content_item_id, revision_number, affiliate_amazon, "
                "affiliate_bookshop, format, created_at) "
                "VALUES (1, 1, 'https://amazon.com/dp/OLD', "
                "'https://bookshop.org/OLD', 'short_hook', CURRENT_TIMESTAMP)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content_packages "
                "(content_item_id, revision_number, affiliate_amazon, "
                "format, created_at) VALUES (1, 2, "
                "'https://amazon.com/dp/ONLY', 'short_hook', "
                "CURRENT_TIMESTAMP)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content_packages "
                "(content_item_id, revision_number, format, created_at) "
                "VALUES (1, 3, 'short_hook', CURRENT_TIMESTAMP)"
            )
    finally:
        engine.dispose()

    # Step 2: apply 0011.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )

    engine = create_engine(url)
    try:
        Session = sessionmaker(bind=engine)
        with Session() as s:
            both, only_amazon, neither = (
                s.query(ContentPackage)
                .order_by(ContentPackage.revision_number)
                .all()
            )
            assert both.cta_links == {
                "amazon_url": "https://amazon.com/dp/OLD",
                "bookshop_url": "https://bookshop.org/OLD",
            }
            assert only_amazon.cta_links == {
                "amazon_url": "https://amazon.com/dp/ONLY"
            }
            assert neither.cta_links is None
    finally:
        engine.dispose()
