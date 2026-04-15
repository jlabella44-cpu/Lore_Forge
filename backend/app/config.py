from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    database_url: str = "sqlite:///./lore_forge.sqlite"

    # AI / Content
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Voice (Phase 2)
    elevenlabs_api_key: str = ""

    # Discovery
    nyt_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    # Affiliate
    amazon_associate_tag: str = ""
    bookshop_affiliate_id: str = ""
    isbndb_api_key: str = ""

    # Publishing (Phase 2)
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""


settings = Settings()
