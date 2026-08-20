"""Last-track camera for the NIU integration."""

from __future__ import annotations

import asyncio
import json
import logging
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

import httpx

from homeassistant.components.camera import Camera
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN
from .coordinator import NiuDataUpdateCoordinator
from .entity import NiuCoordinatorEntity

_LOGGER = logging.getLogger(__name__)
GET_IMAGE_TIMEOUT = 5
GET_IMAGE_TOTAL_TIMEOUT = 8
IMAGE_FAILURE_RETRY_INTERVAL = 60


def _detect_image_content_type(content: bytes) -> str | None:
    """Return the media type identified from common image signatures."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"BM"):
        return "image/bmp"

    stripped = content.lstrip()
    if stripped.startswith(b"<svg") or (
        stripped.startswith(b"<?xml") and b"<svg" in stripped[:512]
    ):
        return "image/svg+xml"
    return None


def _thumbnail_url_candidates(url: str) -> list[str]:
    """Return known NIU thumbnail URL variants without duplicates."""
    parsed = urlsplit(url)
    if not any(
        path in parsed.path for path in ("/track/thumb/", "/track/overseas/thumb/")
    ):
        return [url]

    fk_gateway = parsed.hostname == "s.niucache.com" and parsed.path.startswith(
        "/app-api-fk/"
    )
    direct_path = parsed.path.removeprefix("/app-api-fk") if fk_gateway else parsed.path

    domestic_path = direct_path.replace("/track/overseas/thumb/", "/track/thumb/")
    overseas_path = domestic_path.replace("/track/thumb/", "/track/overseas/thumb/")
    if fk_gateway:
        gateway_domestic_path = parsed.path.replace(
            "/track/overseas/thumb/", "/track/thumb/"
        )
        variants = [
            urlunsplit(parsed._replace(path=gateway_domestic_path)),
            url,
            urlunsplit(
                parsed._replace(netloc="app-api-fk.niu.com", path=domestic_path)
            ),
            urlunsplit(
                parsed._replace(netloc="app-api-fk.niu.com", path=overseas_path)
            ),
        ]
    else:
        variants = [
            url,
            urlunsplit(
                parsed._replace(netloc="app-api.niucache.com", path=domestic_path)
            ),
            urlunsplit(
                parsed._replace(netloc="app-api-fk.niu.com", path=overseas_path)
            ),
            urlunsplit(
                parsed._replace(netloc="app-api-fk.niu.com", path=domestic_path)
            ),
            urlunsplit(parsed._replace(netloc="app-api.niu.com", path=domestic_path)),
        ]
    return list(dict.fromkeys(variants))


def _thumbnail_path_type(url: str) -> str:
    """Describe a thumbnail path without exposing its ride identifier."""
    path = urlsplit(url).path
    if "/track/overseas/thumb/" in path:
        return "overseas"
    if "/track/thumb/" in path:
        return "domestic"
    return "other"


def _invalid_image_description(content: bytes) -> str:
    """Describe a NIU JSON error without logging the full response body."""
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return f"unrecognized {len(content)}-byte response"

    if not isinstance(payload, dict):
        return "JSON response"
    description = payload.get("desc")
    status = payload.get("status")
    if description:
        return f"NIU status {status}: {description}"
    return "JSON response"


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the last-track camera from a config entry."""
    coordinator: NiuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LastTrackCamera(hass, coordinator)])


class LastTrackCamera(NiuCoordinatorEntity, Camera):
    """Still-image camera showing the latest NIU track thumbnail."""

    def __init__(self, hass, coordinator: NiuDataUpdateCoordinator) -> None:
        NiuCoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self.hass = hass
        self._api = coordinator.data
        self._attr_name = f"{self._api.sensor_prefix} Last Track Camera"
        # Preserve GenericCamera's previous identifier to avoid a duplicate entity.
        self._attr_unique_id = self._attr_name
        self._attr_is_streaming = False
        self._last_url: str | None = None
        self._last_image: bytes | None = None
        self._failed_url: str | None = None
        self._failure_retry_at = 0.0

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the cached image or download it when the URL changed."""
        last_track_url = self._api.getDataTrack("track_thumb")
        if not last_track_url:
            _LOGGER.debug("No NIU last-track thumbnail URL available")
            return self._last_image
        if last_track_url == self._last_url and self._last_image is not None:
            return self._last_image
        if last_track_url == self._failed_url and monotonic() < self._failure_retry_at:
            return self._last_image

        candidates = _thumbnail_url_candidates(last_track_url)
        _LOGGER.debug(
            "Trying %d NIU last-track thumbnail candidate(s) "
            "(source host: %s, path type: %s)",
            len(candidates),
            urlsplit(last_track_url).hostname or "relative",
            _thumbnail_path_type(last_track_url),
        )
        client = get_async_client(self.hass, verify_ssl=True)
        try:
            async with asyncio.timeout(GET_IMAGE_TOTAL_TIMEOUT):
                for candidate_url in candidates:
                    candidate_host = urlsplit(candidate_url).hostname or "relative"
                    candidate_path_type = _thumbnail_path_type(candidate_url)
                    try:
                        response = await client.get(
                            candidate_url,
                            timeout=GET_IMAGE_TIMEOUT,
                            follow_redirects=True,
                        )
                        response.raise_for_status()
                    except httpx.TimeoutException:
                        _LOGGER.warning(
                            "Timeout while fetching NIU last-track image candidate "
                            "(host: %s, path type: %s)",
                            candidate_host,
                            candidate_path_type,
                        )
                        continue
                    except httpx.HTTPStatusError as err:
                        status_code = getattr(
                            getattr(err, "response", None), "status_code", "unknown"
                        )
                        _LOGGER.warning(
                            "Could not fetch NIU last-track image candidate "
                            "(host: %s, path type: %s): HTTP %s",
                            candidate_host,
                            candidate_path_type,
                            status_code,
                        )
                        continue
                    except httpx.RequestError:
                        _LOGGER.warning(
                            "Could not fetch NIU last-track image candidate "
                            "(host: %s, path type: %s): request failed",
                            candidate_host,
                            candidate_path_type,
                        )
                        continue

                    content_type = (
                        response.headers.get("content-type", "")
                        .partition(";")[0]
                        .strip()
                        .lower()
                    )
                    if content_type and not content_type.startswith("image/"):
                        _LOGGER.warning(
                            "NIU last-track thumbnail returned invalid content type: %s",
                            content_type,
                        )
                        continue
                    if not response.content:
                        _LOGGER.warning(
                            "NIU last-track thumbnail returned an empty response"
                        )
                        continue

                    detected_content_type = _detect_image_content_type(response.content)
                    if detected_content_type is None:
                        _LOGGER.warning(
                            "NIU last-track thumbnail returned invalid image data: %s",
                            _invalid_image_description(response.content),
                        )
                        continue

                    self.content_type = detected_content_type
                    self._last_image = response.content
                    self._last_url = last_track_url
                    self._failed_url = None
                    self._failure_retry_at = 0.0
                    _LOGGER.debug(
                        "Fetched NIU last-track thumbnail (%d bytes, %s)",
                        len(response.content),
                        detected_content_type,
                    )
                    return self._last_image
        except TimeoutError:
            _LOGGER.warning(
                "Timed out while fetching NIU last-track thumbnail candidates"
            )
        except asyncio.CancelledError:
            self._failed_url = last_track_url
            self._failure_retry_at = monotonic() + IMAGE_FAILURE_RETRY_INTERVAL
            raise

        self._failed_url = last_track_url
        self._failure_retry_at = monotonic() + IMAGE_FAILURE_RETRY_INTERVAL
        return self._last_image
