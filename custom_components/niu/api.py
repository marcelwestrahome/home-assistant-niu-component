from datetime import datetime
import hashlib
import logging
from threading import Lock
from time import gmtime, monotonic, strftime
from typing import Any

import requests

from .const import (
    ACCOUNT_BASE_URL,
    API_BASE_URL,
    LOGIN_URI,
    MOTOR_BATTERY_API_URI,
    MOTOR_INDEX_API_URI,
    MOTOINFO_ALL_API_URI,
    MOTOINFO_LIST_API_URI,
    TRACK_LIST_API_URI,
)

_LOGGER = logging.getLogger(__name__)

APP_ID = "niu_ktdrr960"
REQUEST_TIMEOUT = (10, 30)
TOKEN_REFRESH_MARGIN = 5 * 60
TOKEN_REFRESH_FALLBACK = 22 * 60 * 60


class NiuApiError(Exception):
    """Base exception for NIU API failures."""


class NiuConnectionError(NiuApiError):
    """The NIU service could not be reached."""


class NiuAuthenticationError(NiuApiError):
    """NIU rejected the current authentication."""


class NiuHttpError(NiuApiError):
    """NIU returned an unexpected HTTP client error."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"NIU API returned HTTP {status_code}")
        self.status_code = status_code


class NiuServerError(NiuApiError):
    """NIU returned a server-side error."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"NIU API returned server error HTTP {status_code}")
        self.status_code = status_code


class NiuRateLimitError(NiuApiError):
    """NIU rate-limited the client."""

    def __init__(self, retry_after: int | None) -> None:
        message = "NIU API rate limit exceeded"
        if retry_after is not None:
            message += f"; retry after {retry_after} seconds"
        super().__init__(message)
        self.retry_after = retry_after


class NiuResponseError(NiuApiError):
    """NIU returned an invalid JSON document or an API-level error."""

    def __init__(self, message: str, niu_status: object | None = None) -> None:
        super().__init__(message)
        self.niu_status = niu_status


class NiuVehicleNotFoundError(NiuApiError):
    """The selected vehicle does not exist in the NIU account."""

    def __init__(self, vehicle: int | str) -> None:
        super().__init__(f"NIU vehicle {vehicle} does not exist")
        self.vehicle = vehicle


class NiuNoVehiclesError(NiuApiError):
    """The NIU account does not contain any vehicles."""


class NiuApi:
    def __init__(
        self,
        username,
        password,
        scooter_id,
        language="en-US",
        timezone="UTC",
        vehicle_sn=None,
    ) -> None:
        self.username = username
        self.password = password
        self.scooter_id = int(scooter_id)
        self.vehicle_sn = str(vehicle_sn) if vehicle_sn else None
        self.language = language
        self.timezone = timezone

        self.token = None
        self.refresh_token = None
        self._token_refresh_at = None
        self._auth_generation = 0
        self._auth_lock = Lock()

        self.dataBat = None
        self.dataMoto = None
        self.dataMotoInfo = None
        self.dataTrackInfo = None
        self.sn = None
        self.sensor_prefix = ""

    @classmethod
    def from_hass(cls, hass, username, password, scooter_id, vehicle_sn=None):
        """Create NiuApi with locale settings from Home Assistant config."""
        language = hass.config.language
        # Only append country if language is a bare code (e.g. "en"),
        # not if it already includes a region (e.g. "en-GB", "zh-Hans")
        if hass.config.country and "-" not in language:
            language = f"{language}-{hass.config.country}"
        return cls(
            username,
            password,
            scooter_id,
            vehicle_sn=vehicle_sn,
            language=language,
            timezone=str(hass.config.time_zone),
        )

    def initialize(self):
        """Authenticate and load vehicle metadata without polling entity data."""
        self.select_vehicle(self.get_vehicles(), self.vehicle_sn)

    def get_vehicles(self):
        """Authenticate and return the vehicles available to the account."""
        self.get_token()
        vehicles = self.get_vehicles_info(MOTOINFO_LIST_API_URI)
        try:
            items = vehicles["data"]["items"]
        except (KeyError, TypeError) as err:
            raise NiuResponseError("NIU vehicle list has an unexpected format") from err

        if not isinstance(items, list):
            raise NiuResponseError("NIU vehicle list has an unexpected format")
        if not items:
            raise NiuNoVehiclesError("No vehicles found in the NIU account")
        if any(
            not isinstance(vehicle, dict)
            or not vehicle.get("sn_id")
            or not vehicle.get("scooter_name")
            for vehicle in items
        ):
            raise NiuResponseError("NIU vehicle list has an unexpected format")
        return items

    def select_vehicle(self, items, vehicle_sn=None):
        """Select a vehicle by serial number, falling back to its legacy index."""
        if vehicle_sn is not None:
            try:
                scooter_id = next(
                    index
                    for index, vehicle in enumerate(items)
                    if str(vehicle.get("sn_id")) == str(vehicle_sn)
                )
            except StopIteration as err:
                raise NiuVehicleNotFoundError(vehicle_sn) from err
        else:
            scooter_id = self.scooter_id
            if scooter_id < 0 or scooter_id >= len(items):
                raise NiuVehicleNotFoundError(scooter_id)

        try:
            vehicle = items[scooter_id]
            sn = vehicle["sn_id"]
            scooter_name = vehicle["scooter_name"]
        except (KeyError, TypeError) as err:
            raise NiuResponseError("NIU vehicle list has an unexpected format") from err
        if not sn or not scooter_name:
            raise NiuResponseError("NIU vehicle list has an unexpected format")

        self.scooter_id = scooter_id
        self.sn = str(sn)
        self.vehicle_sn = self.sn
        self.sensor_prefix = str(scooter_name)

    def get_token(self):
        """Authenticate with username and password and return an access token."""
        self._password_login()
        return self.token

    def refresh_access_token(self):
        """Renew the current access token using NIU's refresh token grant."""
        if not self.refresh_token:
            raise NiuAuthenticationError("NIU did not provide a refresh token")

        data = {
            "app_id": APP_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        self._store_token(self._request_token(data))
        return self.token

    def _password_login(self):
        password_hash = hashlib.md5(self.password.encode("utf-8")).hexdigest()
        data = {
            "account": self.username,
            "password": password_hash,
            "grant_type": "password",
            "scope": "base",
            "app_id": APP_ID,
        }
        self._store_token(self._request_token(data))

    def _request_token(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            response = requests.post(
                ACCOUNT_BASE_URL + LOGIN_URI,
                data=data,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise NiuConnectionError("Could not reach NIU authentication service") from err

        payload = self._parse_response(response, authentication_request=True)
        try:
            token_data = payload["data"]["token"]
            access_token = token_data["access_token"]
        except (KeyError, TypeError) as err:
            raise NiuAuthenticationError(
                "NIU authentication response did not contain an access token"
            ) from err
        if not isinstance(token_data, dict) or not access_token:
            raise NiuAuthenticationError("NIU returned an invalid access token")
        return token_data

    def _store_token(self, token_data: dict[str, Any]) -> None:
        self.token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            self.refresh_token = refresh_token

        refresh_delay = TOKEN_REFRESH_FALLBACK
        expires_in = token_data.get("expires_in")
        if expires_in is not None:
            try:
                refresh_delay = max(0, int(expires_in) - TOKEN_REFRESH_MARGIN)
            except (TypeError, ValueError):
                _LOGGER.debug("NIU returned an invalid expires_in value")
        self._token_refresh_at = monotonic() + refresh_delay
        self._auth_generation += 1

    def _ensure_access_token(self) -> None:
        if not self.token:
            with self._auth_lock:
                if not self.token:
                    self._password_login()
            return

        if self._token_refresh_at is None or monotonic() < self._token_refresh_at:
            return

        with self._auth_lock:
            if self._token_refresh_at is None or monotonic() < self._token_refresh_at:
                return
            try:
                if self.refresh_token:
                    self.refresh_access_token()
                else:
                    self._password_login()
            except NiuAuthenticationError:
                self._password_login()
            except NiuApiError as err:
                # The existing token may still be valid. Let the data request decide;
                # a 401 response will trigger the full recovery path below.
                _LOGGER.warning("Could not proactively refresh NIU token: %s", err)

    def _recover_authentication(self, attempted_generation: int) -> None:
        with self._auth_lock:
            if self._auth_generation != attempted_generation:
                return

            if self.refresh_token:
                try:
                    self.refresh_access_token()
                    return
                except NiuApiError as err:
                    _LOGGER.warning("NIU token refresh failed; logging in again: %s", err)

            self._password_login()

    def _authenticated_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        self._ensure_access_token()
        attempted_generation = self._auth_generation
        response = self._perform_request(method, path, headers=headers, **kwargs)

        if response.status_code == 401:
            self._recover_authentication(attempted_generation)
            response = self._perform_request(method, path, headers=headers, **kwargs)
            if response.status_code == 401:
                raise NiuAuthenticationError(
                    "NIU rejected authentication after token recovery"
                )

        return self._parse_response(response)

    def _perform_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        request_headers = {**(headers or {}), "token": self.token}
        request_method = requests.get if method == "GET" else requests.post
        try:
            return request_method(
                API_BASE_URL + path,
                headers=request_headers,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
        except requests.exceptions.RequestException as err:
            raise NiuConnectionError("Could not communicate with NIU API") from err

    @staticmethod
    def _parse_retry_after(response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    def _parse_response(
        self, response, *, authentication_request: bool = False
    ) -> dict[str, Any]:
        status_code = response.status_code
        if status_code == 429:
            raise NiuRateLimitError(self._parse_retry_after(response))
        if status_code >= 500:
            raise NiuServerError(status_code)
        if status_code in (401, 403) or (
            authentication_request and status_code == 400
        ):
            raise NiuAuthenticationError(
                f"NIU rejected authentication with HTTP {status_code}"
            )
        if status_code >= 400:
            raise NiuHttpError(status_code)

        try:
            payload = response.json()
        except (ValueError, requests.exceptions.RequestException) as err:
            raise NiuResponseError("NIU returned invalid JSON") from err
        if not isinstance(payload, dict):
            raise NiuResponseError("NIU returned an unexpected JSON document")

        niu_status = payload.get("status", 0)
        if niu_status != 0:
            description = payload.get("desc") or "unknown NIU API error"
            if authentication_request:
                raise NiuAuthenticationError(
                    f"NIU authentication failed with status {niu_status}: {description}"
                )
            raise NiuResponseError(
                f"NIU API returned status {niu_status}: {description}",
                niu_status=niu_status,
            )
        return payload

    def _locale_headers(self) -> dict[str, str]:
        """Build the locale-aware headers shared by the GET endpoints."""
        is_chinese = self.language.startswith("zh")
        client_id = "Domestic" if is_chinese else "Overseas"
        return {
            "Accept-Language": self.language,
            "user-agent": f"manager/4.10.4 (android; IN2020 11);lang={self.language};clientIdentifier={client_id};timezone={self.timezone};model=IN2020;deviceName=IN2020;ostype=android",
        }

    def get_vehicles_info(self, path):
        return self._authenticated_request(
            "GET", path, headers=self._locale_headers()
        )

    def get_info(
        self,
        path,
    ):
        params = {"sn": self.sn}
        return self._authenticated_request(
            "GET", path, headers=self._locale_headers(), params=params
        )

    def post_info(
        self,
        path,
    ):
        headers = {"Accept-Language": self.language}
        return self._authenticated_request(
            "POST", path, headers=headers, data={"sn": self.sn}
        )

    def post_info_track(self, path):
        is_chinese = self.language.startswith("zh")
        client_id = "Domestic" if is_chinese else "Overseas"
        headers = {
            "Accept-Language": self.language,
            "User-Agent": f"manager/1.0.0 (identifier);clientIdentifier={client_id}",
        }
        return self._authenticated_request(
            "POST",
            path,
            headers=headers,
            json={"index": "0", "pagesize": 10, "sn": self.sn},
        )

    def getDataBatA(self, id_field):
        try:
            return self.dataBat["data"]["batteries"]["compartmentA"][id_field]
        except (KeyError, TypeError):
            return None

    def hasSecondBattery(self):
        try:
            return "compartmentB" in self.dataBat["data"]["batteries"]
        except (KeyError, TypeError):
            return False

    def getDataBatB(self, id_field):
        try:
            return self.dataBat["data"]["batteries"]["compartmentB"][id_field]
        except (KeyError, TypeError):
            return None

    def getDataMoto(self, id_field):
        try:
            return self.dataMoto["data"][id_field]
        except (KeyError, TypeError):
            return None

    def getDataDist(self, id_field):
        try:
            return self.dataMoto["data"]["lastTrack"][id_field]
        except (KeyError, TypeError):
            return None

    def getDataPos(self, id_field):
        try:
            return self.dataMoto["data"]["postion"][id_field]
        except (KeyError, TypeError):
            return None

    def getDataOverall(self, id_field):
        try:
            return self.dataMotoInfo["data"][id_field]
        except (KeyError, TypeError):
            return None

    def getDataTrack(self, id_field):
        try:
            value = self.dataTrackInfo["data"][0][id_field]
        except (IndexError, KeyError, TypeError):
            return None

        if id_field in ("startTime", "endTime"):
            try:
                return datetime.fromtimestamp(value / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (OSError, TypeError, ValueError):
                return None
        if id_field == "ridingtime":
            try:
                return strftime("%H:%M:%S", gmtime(value))
            except (OSError, TypeError, ValueError):
                return None
        if id_field == "track_thumb":
            if not isinstance(value, str):
                return None
            thumburl = value
            # Rewrite domestic CDN URLs to overseas; skip if already overseas
            if "app-api.niucache.com" in thumburl:
                thumburl = thumburl.replace(
                    "app-api.niucache.com", "app-api-fk.niu.com"
                )
            if "/track/thumb/" in thumburl and "/track/overseas/thumb/" not in thumburl:
                thumburl = thumburl.replace("/track/thumb/", "/track/overseas/thumb/")
            return thumburl
        return value

    def updateBat(self):
        result = self.get_info(MOTOR_BATTERY_API_URI)
        if result is not None:
            self.dataBat = result

    def updateMoto(self):
        result = self.get_info(MOTOR_INDEX_API_URI)
        if result is not None:
            self.dataMoto = result

    def updateMotoInfo(self):
        result = self.post_info(MOTOINFO_ALL_API_URI)
        if result is not None:
            self.dataMotoInfo = result

    def updateTrackInfo(self):
        result = self.post_info_track(TRACK_LIST_API_URI)
        if result is not None:
            self.dataTrackInfo = result
