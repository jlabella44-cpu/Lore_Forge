"""YouTube Shorts upload via the YouTube Data API v3.

Real call shape is below — the upload flow just isn't turned on yet because
it needs a one-time Google OAuth dance. To enable:

  1. Install the deps:
       google-api-python-client google-auth google-auth-oauthlib

  2. Create an OAuth 2.0 Desktop-app client in Google Cloud Console and
     download credentials.json. Point `YOUTUBE_CLIENT_SECRETS` at it.

  3. Run `python -m scripts.auth_google` once (Phase 3 will add this helper)
     — it launches a browser, has you consent, and writes the resulting
     token to `YOUTUBE_TOKEN_FILE`.

  4. Uncomment the body of `upload()` below.

Docs: https://developers.google.com/youtube/v3/docs/videos/insert
Quota: 1,600 units / upload. Default daily quota: 10,000 units → ~6 uploads/day.
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings


def upload(
    video_path: str | Path,
    *,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "unlisted",
) -> str:
    """Upload an mp4 to YouTube as a Short. Returns the video ID.

    Shorts are detected from the video aspect ratio (9:16) + duration
    (< 60 seconds recommended). We don't set a shorts-specific flag —
    the `#shorts` in description/hashtags is the standard marker.
    """
    if not settings.youtube_client_id or not settings.youtube_client_secret:
        raise RuntimeError(
            "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET not set; "
            "upload path is stubbed. See services/youtube.py for setup."
        )

    # Real implementation shape (uncomment + install deps to enable):
    #
    # from googleapiclient.discovery import build
    # from googleapiclient.http import MediaFileUpload
    # from google.oauth2.credentials import Credentials
    #
    # creds = Credentials.from_authorized_user_file(settings.youtube_token_file)
    # yt = build("youtube", "v3", credentials=creds)
    # body = {
    #     "snippet": {
    #         "title": title,
    #         "description": description,
    #         "tags": tags,
    #         "categoryId": "22",  # People & Blogs; "24" Entertainment
    #     },
    #     "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    # }
    # media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    # req = yt.videos().insert(part=",".join(body), body=body, media_body=media)
    # response = None
    # while response is None:
    #     _, response = req.next_chunk()
    # return response["id"]

    raise NotImplementedError(
        "YouTube Shorts upload not yet wired — see services/youtube.py for "
        "the OAuth bootstrap steps."
    )
