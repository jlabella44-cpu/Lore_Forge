from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db_url import resolve_sqlite_url
from app.paths import resolve_repo_root_path

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Storage ----
    database_url: str = "sqlite:///./lore_forge.sqlite"

    @field_validator("database_url")
    @classmethod
    def _anchor_sqlite_at_repo_root(cls, v: str) -> str:
        # Normalize relative sqlite paths to repo-root absolute, so the
        # backend (cwd=backend/) and alembic (cwd=db/) can't drift onto
        # two different files. Non-sqlite URLs pass through unchanged.
        return resolve_sqlite_url(v, REPO_ROOT)

    # ---- Renderer paths ----
    # Normalized against the repo root by `_anchor_path_at_repo_root` below,
    # so uvicorn from backend/ and tests from tests/ see the same absolute
    # locations. Same bug class as the DATABASE_URL anchoring above.
    renders_dir: str = "./renders"
    music_dir: str = "./backend/assets/music"
    remotion_dir: str = "./remotion"

    @field_validator("renders_dir", "music_dir", "remotion_dir")
    @classmethod
    def _anchor_path_at_repo_root(cls, v: str) -> str:
        return resolve_repo_root_path(v, REPO_ROOT)

    # ---- APScheduler ----
    # Weekly discovery cron is opt-in so `uvicorn --reload` doesn't fire
    # real API calls on every code change in dev.
    discovery_cron_enabled: bool = False
    discovery_cron_day: str = "mon"
    discovery_cron_hour: int = 6

    # ---- Cost guardrail ----
    # Daily spending cap in cents. When the rolling 24h cost exceeds this,
    # generate + render enqueue calls return 429 until the window clears.
    # Set to 0 or a negative value to disable.
    cost_daily_budget_cents: int = 500  # $5.00 default

    # ---- Render retention ----
    # Rendered videos for books that never got published pile up on disk.
    # `POST /packages/prune-renders` deletes `{renders_dir}/{pkg_id}/` for
    # unpublished packages whose last render is older than this many days.
    # Set to 0 or negative to disable (the endpoint will 400).
    render_retention_days: int = 30

    # ---- Image asset cache ----
    # Dedups image provider API calls across failed/rerun jobs by hashing
    # (provider, model, aspect, prompt) and caching the bytes under
    # `{renders_dir}/_cache/images/`. Disable to force every render to
    # re-issue fresh calls (useful when debugging a provider).
    image_cache_enabled: bool = True
    # LRU cutoff for `prune_stale_image_cache` — rows (and their blobs)
    # with `last_used_at` older than this are deleted.
    image_cache_retention_days: int = 30

    # ---- LLM keys ----
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-6"

    openai_api_key: str = ""
    openai_script_model: str = "gpt-4o"
    openai_meta_model: str = "gpt-4o-mini"

    # Dashscope hosts both Qwen (text) and Wanx (images). Use the OpenAI-compatible
    # endpoint for Qwen chat; the native `dashscope` SDK for Wanx images.
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    # ---- Provider routing ----
    # SCRIPT_PROVIDER handles creative script + image prompts (quality-sensitive).
    # META_PROVIDER handles classify + per-platform titles/hashtags (formulaic).
    script_provider: str = "claude"          # claude | openai | qwen
    meta_provider: str = "qwen"              # claude | openai | qwen
    tts_provider: str = "openai"             # openai | kokoro | dashscope | elevenlabs
    tts_model: str = "tts-1-hd"             # tts-1 (fast/flat) | tts-1-hd (expressive)
    image_provider: str = "wanx"             # wanx | dalle | imagen | replicate | sdxl_local | midjourney_manual

    # ---- Voice (optional upgrades) ----
    elevenlabs_api_key: str = ""

    # ---- Discovery ----
    nyt_api_key: str = ""
    reddit_user_agent: str = "lore-forge/0.1 (book-discovery bot)"
    firecrawl_api_key: str = ""

    # Which sources run on /discover/run and on the weekly cron. Comma-separated.
    # Valid values: nyt, goodreads, amazon_movers, reddit, booktok.
    sources_enabled: str = "nyt"

    # ---- Affiliate ----
    amazon_associate_tag: str = ""
    bookshop_affiliate_id: str = ""
    isbndb_api_key: str = ""

    # ---- Quality gate (flag-gated, off by default) ----
    # When on, each generated script is checked for banned vocabulary and
    # dossier citation; on failure the script is regenerated once with
    # feedback before scene prompts run.
    quality_gate: bool = False

    # ---- Publishing (Phase 2) — shorts-only targets ----
    # TikTok, YT Shorts (via Data API), IG Reels + Threads (via Meta Graph).
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""


settings = Settings()
