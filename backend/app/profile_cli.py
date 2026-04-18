"""Command-line interface for Profile management.

Mirrors the `/profiles` HTTP router but operates directly against
SessionLocal so the user doesn't need to have the backend running.
Useful for headless bootstrapping (CI, desktop-build post-install
hooks) and for operators who prefer a terminal over curl.

Usage:
    python -m app.profile_cli list
    python -m app.profile_cli show books
    python -m app.profile_cli export books > books.yaml
    python -m app.profile_cli import path/to/films.yaml
    python -m app.profile_cli import path/to/films.yaml --overwrite
    python -m app.profile_cli import-bundle           # all resources/profiles/*.yaml
    python -m app.profile_cli activate films
    python -m app.profile_cli delete films
    python -m app.profile_cli vars books entity_type=book audience_noun=readers

All commands exit 0 on success, non-zero on any validation or not-
found error with a message on stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from app import db as db_module
from app.config import REPO_ROOT
from app.models.profile import Profile
from app.services import profiles as profile_service


# ---------------------------------------------------------------------------
# Serialization helpers — parallels routers/profiles.py._SERIALIZABLE_COLUMNS
# without importing it (avoids FastAPI-only deps in a CLI-only flow).
# ---------------------------------------------------------------------------


_SERIALIZABLE_COLUMNS = (
    "slug",
    "name",
    "entity_label",
    "description",
    "sources_config",
    "prompts",
    "prompt_variables",
    "taxonomy",
    "cta_fields",
    "render_tones",
)


def _to_yaml_dict(p: Profile) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in _SERIALIZABLE_COLUMNS:
        val = getattr(p, col)
        if val in (None, "", [], {}):
            continue
        out[col] = val
    return out


def _to_row_summary(p: Profile) -> str:
    flag = " *" if p.active else "  "
    return f"{flag} {p.slug:<20} {p.entity_label:<12} {p.name}"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list(_args, db) -> int:
    profiles = profile_service.list_all(db)
    if not profiles:
        print("(no profiles)")
        return 0
    print("  slug                 entity        name")
    for p in profiles:
        print(_to_row_summary(p))
    return 0


def cmd_show(args, db) -> int:
    p = profile_service.get_by_slug(db, args.slug)
    if p is None:
        print(f"profile {args.slug!r} not found", file=sys.stderr)
        return 1
    print(json.dumps(_to_yaml_dict(p), indent=2, default=str))
    return 0


def cmd_export(args, db) -> int:
    p = profile_service.get_by_slug(db, args.slug)
    if p is None:
        print(f"profile {args.slug!r} not found", file=sys.stderr)
        return 1
    yaml.safe_dump(
        _to_yaml_dict(p),
        sys.stdout,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return 0


def _import_one(db, parsed: dict, overwrite: bool) -> tuple[bool, str]:
    """Returns `(ok, message)`. Does not commit — caller does."""
    if not isinstance(parsed, dict):
        return False, "YAML must parse to a mapping at the top level"

    slug = parsed.get("slug")
    if not isinstance(slug, str) or not slug:
        return False, "YAML missing string 'slug'"

    extra = set(parsed) - set(_SERIALIZABLE_COLUMNS)
    if extra:
        return False, f"unknown YAML keys: {sorted(extra)}"

    required = {"slug", "name", "entity_label"}
    missing = required - set(parsed)
    if missing:
        return False, f"YAML missing required keys: {sorted(missing)}"

    existing = profile_service.get_by_slug(db, slug)
    if existing is not None and not overwrite:
        return False, f"profile {slug!r} exists (use --overwrite to replace)"

    if existing is None:
        target = Profile(slug=slug, name="", entity_label="", active=False)
        db.add(target)
    else:
        target = existing

    for col in _SERIALIZABLE_COLUMNS:
        if col in parsed:
            setattr(target, col, parsed[col])
    return True, slug


def cmd_import(args, db) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        return 1
    try:
        parsed = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        print(f"invalid YAML: {exc}", file=sys.stderr)
        return 1

    ok, msg = _import_one(db, parsed, overwrite=args.overwrite)
    if not ok:
        print(msg, file=sys.stderr)
        return 1
    db.commit()
    print(f"imported {msg}")
    return 0


def cmd_import_bundle(args, db) -> int:
    bundle_dir = REPO_ROOT / "resources" / "profiles"
    if not bundle_dir.is_dir():
        print(f"bundle directory missing: {bundle_dir}", file=sys.stderr)
        return 1

    ok_any = False
    for path in sorted(bundle_dir.glob("*.yaml")):
        try:
            parsed = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            print(f"  {path.name}: invalid YAML ({exc})", file=sys.stderr)
            continue
        ok, msg = _import_one(db, parsed, overwrite=args.overwrite)
        if ok:
            db.commit()
            print(f"  imported {msg}")
            ok_any = True
        else:
            print(f"  skipped {path.name}: {msg}", file=sys.stderr)
    return 0 if ok_any else 1


def cmd_activate(args, db) -> int:
    try:
        p = profile_service.set_active(db, args.slug)
    except LookupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    db.commit()
    print(f"activated {p.slug}")
    return 0


def cmd_delete(args, db) -> int:
    p = profile_service.get_by_slug(db, args.slug)
    if p is None:
        print(f"profile {args.slug!r} not found", file=sys.stderr)
        return 1
    if p.active:
        print(
            f"refusing to delete the active profile {args.slug!r}; "
            "activate another profile first",
            file=sys.stderr,
        )
        return 1
    from app.models import ContentItem

    refs = db.query(ContentItem).filter(ContentItem.profile_id == p.id).count()
    if refs:
        print(
            f"refusing to delete {args.slug!r}: {refs} ContentItem rows "
            "still reference it",
            file=sys.stderr,
        )
        return 1
    db.delete(p)
    db.commit()
    print(f"deleted {args.slug}")
    return 0


def cmd_vars(args, db) -> int:
    """Set one or more prompt_variables key=value pairs on a profile."""
    p = profile_service.get_by_slug(db, args.slug)
    if p is None:
        print(f"profile {args.slug!r} not found", file=sys.stderr)
        return 1

    current = dict(p.prompt_variables or {})
    for pair in args.pairs:
        if "=" not in pair:
            print(f"expected key=value, got {pair!r}", file=sys.stderr)
            return 1
        k, v = pair.split("=", 1)
        current[k.strip()] = v.strip()
    p.prompt_variables = current
    db.commit()
    print(json.dumps(current, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m app.profile_cli",
        description="Manage Lore Forge content profiles from the terminal.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all profiles (active marked with *).")

    p_show = sub.add_parser("show", help="Print a profile as JSON.")
    p_show.add_argument("slug")

    p_export = sub.add_parser("export", help="Dump a profile as YAML to stdout.")
    p_export.add_argument("slug")

    p_import = sub.add_parser("import", help="Import a profile from a YAML file.")
    p_import.add_argument("path")
    p_import.add_argument("--overwrite", action="store_true")

    p_bundle = sub.add_parser(
        "import-bundle",
        help="Import every YAML in resources/profiles/.",
    )
    p_bundle.add_argument("--overwrite", action="store_true")

    p_activate = sub.add_parser(
        "activate", help="Mark a profile as the single active one."
    )
    p_activate.add_argument("slug")

    p_delete = sub.add_parser(
        "delete",
        help="Delete an inactive, unreferenced profile.",
    )
    p_delete.add_argument("slug")

    p_vars = sub.add_parser(
        "vars",
        help="Merge one or more key=value pairs into prompt_variables.",
    )
    p_vars.add_argument("slug")
    p_vars.add_argument(
        "pairs",
        nargs="+",
        help="One or more key=value strings (e.g. entity_type=film).",
    )

    return ap


_DISPATCH = {
    "list": cmd_list,
    "show": cmd_show,
    "export": cmd_export,
    "import": cmd_import,
    "import-bundle": cmd_import_bundle,
    "activate": cmd_activate,
    "delete": cmd_delete,
    "vars": cmd_vars,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = _DISPATCH[args.command]
    # Attribute access (not a top-level `from app.db import
    # SessionLocal`) so pytest fixtures that swap
    # `db_module.SessionLocal` to the test engine take effect.
    with db_module.SessionLocal() as db:
        return handler(args, db)


if __name__ == "__main__":
    raise SystemExit(main())
