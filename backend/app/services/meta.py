"""Meta Graph API — Instagram Reels + Threads.

Both sit behind the same Meta OAuth app but hit different endpoints. Both
require a Facebook Business Account, an Instagram Business or Creator account
(for Reels), and `pages_show_list` / `instagram_basic` /
`instagram_content_publish` / `threads_content_publish` scopes as applicable.

Instagram Reels flow
  https://developers.facebook.com/docs/instagram-api/guides/content-publishing#reels

  1. POST /{ig-user-id}/media with media_type=REELS + video_url (must be a
     publicly reachable URL; local file paths don't work — you have to host
     the mp4 first or push it to Meta's media library).
  2. Poll GET /{container-id}?fields=status_code until FINISHED.
  3. POST /{ig-user-id}/media_publish with creation_id=<container_id>.

Threads flow
  https://developers.facebook.com/docs/threads/publish

  1. POST /{threads-user-id}/threads with media_type=VIDEO + video_url +
     text (Threads supports a teaser text separate from the video).
  2. POST /{threads-user-id}/threads_publish with creation_id=<container_id>.
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings


def upload_reels(
    video_url: str,
    *,
    caption: str,
    hashtags: list[str],
) -> str:
    """Publish a Reel. `video_url` MUST be a publicly reachable URL (Meta
    fetches it). Returns the published media ID."""
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise RuntimeError(
            "META_APP_ID / META_APP_SECRET not set; upload path is stubbed. "
            "See services/meta.py for setup."
        )

    # Real implementation shape:
    #
    # import time
    # import httpx
    # access_token = _load_meta_page_access_token()
    # ig_user_id = settings.meta_ig_user_id
    #
    # container = httpx.post(
    #     f"https://graph.facebook.com/v20.0/{ig_user_id}/media",
    #     params={
    #         "media_type": "REELS",
    #         "video_url": video_url,
    #         "caption": caption + "\n\n" + " ".join(hashtags),
    #         "access_token": access_token,
    #     },
    #     timeout=60,
    # ).json()
    # container_id = container["id"]
    #
    # # Wait for Meta to ingest the video
    # while True:
    #     st = httpx.get(
    #         f"https://graph.facebook.com/v20.0/{container_id}",
    #         params={"fields": "status_code", "access_token": access_token},
    #     ).json()
    #     if st.get("status_code") == "FINISHED":
    #         break
    #     if st.get("status_code") == "ERROR":
    #         raise RuntimeError(f"Reels ingest failed: {st}")
    #     time.sleep(5)
    #
    # publish = httpx.post(
    #     f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish",
    #     params={"creation_id": container_id, "access_token": access_token},
    # ).json()
    # return publish["id"]

    raise NotImplementedError(
        "Instagram Reels upload not yet wired — see services/meta.py. "
        "Requires a Facebook Business account + Instagram Business/Creator "
        "account + `instagram_content_publish` scope."
    )


def upload_threads(
    video_url: str,
    *,
    text: str,
    hashtags: list[str],
) -> str:
    """Post a Threads video + teaser. Returns the thread id."""
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise RuntimeError(
            "META_APP_ID / META_APP_SECRET not set; upload path is stubbed. "
            "See services/meta.py for setup."
        )

    # Real implementation shape:
    #
    # import httpx
    # access_token = _load_threads_access_token()
    # threads_user_id = settings.meta_threads_user_id
    #
    # container = httpx.post(
    #     f"https://graph.threads.net/v1.0/{threads_user_id}/threads",
    #     params={
    #         "media_type": "VIDEO",
    #         "video_url": video_url,
    #         "text": text + "\n\n" + " ".join(hashtags),
    #         "access_token": access_token,
    #     },
    # ).json()
    # container_id = container["id"]
    #
    # publish = httpx.post(
    #     f"https://graph.threads.net/v1.0/{threads_user_id}/threads_publish",
    #     params={"creation_id": container_id, "access_token": access_token},
    # ).json()
    # return publish["id"]

    raise NotImplementedError(
        "Threads upload not yet wired — see services/meta.py. "
        "Requires a Threads account linked to a Meta developer app with "
        "`threads_content_publish` scope."
    )
