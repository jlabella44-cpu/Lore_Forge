"""TikTok upload via the Content Posting API (Direct Post).

Blocked on app approval — TikTok requires a sandbox-first review and your
Content Posting API scope has to be approved for Direct Post. Self-service
upload flow:

  https://developers.tiktok.com/doc/content-posting-api-reference-direct-post

High level:
  1. Get an OAuth 2.0 token with scope `video.publish` for a Business or
     Creator account.
  2. POST /v2/post/publish/video/init/ with `source=FILE_UPLOAD` → returns
     `upload_url` + `publish_id`.
  3. PUT the mp4 bytes to `upload_url` in chunked requests.
  4. Poll /v2/post/publish/status/fetch/ with the publish_id until the
     status is `PUBLISH_COMPLETE` (or error).

Quotas: small per-day publish limit during sandbox; increases after approval.
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings


def upload(
    video_path: str | Path,
    *,
    caption: str,
    hashtags: list[str],
    privacy: str = "SELF_ONLY",
) -> str:
    """Upload an mp4 to TikTok. Returns the publish_id (platform's handle).

    `privacy` in sandbox must be SELF_ONLY; production accounts can use
    PUBLIC_TO_EVERYONE / MUTUAL_FOLLOW_FRIENDS.
    """
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise RuntimeError(
            "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET not set; "
            "upload path is stubbed. See services/tiktok.py for setup."
        )

    # Real implementation shape (requires approved TikTok app):
    #
    # import httpx
    # access_token = _load_tiktok_access_token()  # refreshed from stored refresh_token
    # init = httpx.post(
    #     "https://open.tiktokapis.com/v2/post/publish/video/init/",
    #     headers={"Authorization": f"Bearer {access_token}"},
    #     json={
    #         "post_info": {
    #             "title": caption,
    #             "privacy_level": privacy,
    #             "disable_comment": False,
    #             "disable_duet": True,
    #             "disable_stitch": True,
    #         },
    #         "source_info": {
    #             "source": "FILE_UPLOAD",
    #             "video_size": Path(video_path).stat().st_size,
    #             "chunk_size": 10_000_000,
    #             "total_chunk_count": 1,
    #         },
    #     },
    #     timeout=30,
    # ).json()
    # publish_id = init["data"]["publish_id"]
    # upload_url = init["data"]["upload_url"]
    #
    # # Upload the mp4 bytes
    # with open(video_path, "rb") as f:
    #     httpx.put(upload_url, content=f.read(), headers={"Content-Type": "video/mp4"},
    #               timeout=600).raise_for_status()
    #
    # # Poll until complete (or failed)
    # while True:
    #     st = httpx.post(
    #         "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
    #         headers={"Authorization": f"Bearer {access_token}"},
    #         json={"publish_id": publish_id},
    #     ).json()
    #     status = st["data"]["status"]
    #     if status == "PUBLISH_COMPLETE":
    #         return publish_id
    #     if status.startswith("FAIL"):
    #         raise RuntimeError(f"TikTok publish failed: {st}")
    #     time.sleep(5)

    raise NotImplementedError(
        "TikTok upload not yet wired — see services/tiktok.py. Requires app "
        "review approval for the `video.publish` scope."
    )
