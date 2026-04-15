from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Storage ----
    database_url: str = "sqlite:///./lore_forge.sqlite"

    # ---- Renderer paths (all resolved relative to the backend/ cwd) ----
    renders_dir: str = "./renders"
    music_dir: str = "./assets/music"
    remotion_dir: str = "../remotion"

    # ---- APScheduler ----
    # Weekly discovery cron is opt-in so `uvicorn --reload` doesn't fire
    # real API calls on every code change in dev.
    discovery_cron_enabled: bool = False
    discovery_cron_day: str = "mon"
    discovery_cron_hour: int = 6

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

    # ---- Publishing (Phase 2) — shorts-only targets ----
    # TikTok, YT Shorts (via Data API), IG Reels + Threads (via Meta Graph).
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""


settings = Settings()
