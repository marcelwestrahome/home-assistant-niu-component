"""Small NIU API simulator for the local Home Assistant environment."""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
from urllib.parse import parse_qs, urlsplit


TRACK_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

TOKEN_RESPONSE = {
    "status": 0,
    "data": {
        "token": {
            "access_token": "local-access-token",
            "refresh_token": "local-refresh-token",
            "expires_in": 86400,
        }
    },
}

VEHICLES = {
    "LOCAL-NIU-001": {
        "scooter_name": "Mock NIU One",
        "/v3/motor_data/battery_info": {
            "batteries": {
                "compartmentA": {
                    "bmsId": "MOCK-BMS-A1",
                    "batteryCharging": 78,
                    "isConnected": True,
                    "chargedTimes": 42,
                    "temperatureDesc": "Normal",
                    "temperature": 21,
                    "gradeBattery": 96,
                },
                "compartmentB": {
                    "bmsId": "MOCK-BMS-B1",
                    "batteryCharging": 64,
                    "isConnected": True,
                    "chargedTimes": 39,
                    "temperatureDesc": "Normal",
                    "temperature": 22,
                    "gradeBattery": 94,
                },
            }
        },
        "/v5/scooter/motor_data/index_info": {
            "nowSpeed": 0,
            "isConnected": True,
            "isCharging": False,
            "lockStatus": True,
            "leftTime": 0,
            "estimatedMileage": 58,
            "centreCtrlBattery": 91,
            "lastTrack": {"distance": 4200, "ridingTime": 900},
            "postion": {"lng": 13.6167, "lat": 47.6422},
        },
        "/motoinfo/overallTally": {"totalMileage": 1234.5, "bindDaysCount": 365},
        "/v5/track/list/v2": [
            {
                "startTime": 1788253200000,
                "endTime": 1788254100000,
                "distance": 4200,
                "avespeed": 16.8,
                "ridingtime": 900,
                "track_thumb": "http://mock-niu:8080/track.png",
            }
        ],
    },
    "LOCAL-NIU-002": {
        "scooter_name": "Mock NIU Two",
        "/v3/motor_data/battery_info": {
            "batteries": {
                "compartmentA": {
                    "batteryCharging": 54,
                    "isConnected": True,
                    "chargedTimes": 17,
                    "temperatureDesc": "Warm",
                    "temperature": 24,
                    "gradeBattery": 88,
                }
            }
        },
        "/v5/scooter/motor_data/index_info": {
            "nowSpeed": 23,
            "isConnected": True,
            "isCharging": False,
            "lockStatus": False,
            "leftTime": 0,
            "estimatedMileage": 36,
            "centreCtrlBattery": 84,
            "lastTrack": {"distance": 8100, "ridingTime": 1200},
            "postion": {"lng": 16.3738, "lat": 48.2082},
        },
        "/motoinfo/overallTally": {"totalMileage": 543.2, "bindDaysCount": 120},
        "/v5/track/list/v2": [
            {
                "startTime": 1788339600000,
                "endTime": 1788340800000,
                "distance": 8100,
                "avespeed": 24.3,
                "ridingtime": 1200,
                "track_thumb": "http://mock-niu:8080/track.png",
            }
        ],
    },
}


def request_serial_number(url: str, body: bytes, content_type: str) -> str | None:
    values: dict[str, object] = parse_qs(urlsplit(url).query)
    if body:
        try:
            if content_type.partition(";")[0] == "application/json":
                decoded = json.loads(body)
                if isinstance(decoded, dict):
                    values.update(decoded)
            else:
                values.update(parse_qs(body.decode()))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    serial_number = values.get("sn")
    if isinstance(serial_number, list):
        return serial_number[-1]
    return serial_number if isinstance(serial_number, str) else None


def response_for(path: str, serial_number: str | None = None) -> dict | None:
    if path == "/v3/api/oauth2/token":
        return TOKEN_RESPONSE
    if path == "/v5/scooter/list":
        return {
            "status": 0,
            "data": {
                "items": [
                    {"sn_id": sn, "scooter_name": vehicle["scooter_name"]}
                    for sn, vehicle in VEHICLES.items()
                ]
            },
        }

    vehicle = VEHICLES.get(serial_number)
    data = vehicle.get(path) if vehicle else None
    return {"status": 0, "data": data} if data is not None else None


class Handler(BaseHTTPRequestHandler):
    def _respond(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        path = urlsplit(self.path).path
        if path == "/track.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(TRACK_IMAGE)))
            self.end_headers()
            self.wfile.write(TRACK_IMAGE)
            return

        payload = response_for(
            path,
            request_serial_number(
                self.path, body, self.headers.get("Content-Type", "")
            ),
        )
        status = 200 if payload is not None else 404
        body = json.dumps(payload or {"status": 404, "desc": "unknown mock endpoint"}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _respond
    do_POST = _respond


def self_test() -> None:
    assert TRACK_IMAGE.startswith(b"\x89PNG\r\n\x1a\n")
    vehicles = response_for("/v5/scooter/list")["data"]["items"]
    assert [vehicle["sn_id"] for vehicle in vehicles] == list(VEHICLES)
    first = response_for("/v3/motor_data/battery_info", "LOCAL-NIU-001")
    second = response_for("/v3/motor_data/battery_info", "LOCAL-NIU-002")
    assert first["data"]["batteries"]["compartmentA"]["batteryCharging"] == 78
    assert first["data"]["batteries"]["compartmentB"]["batteryCharging"] == 64
    assert second["data"]["batteries"]["compartmentA"]["batteryCharging"] == 54
    assert "compartmentB" not in second["data"]["batteries"]
    assert response_for("/v3/motor_data/battery_info", "UNKNOWN") is None
    assert request_serial_number("/?sn=LOCAL-NIU-001", b"", "") == "LOCAL-NIU-001"
    assert request_serial_number("/", b"sn=LOCAL-NIU-002", "") == "LOCAL-NIU-002"
    assert (
        request_serial_number("/", b'{"sn":"LOCAL-NIU-002"}', "application/json")
        == "LOCAL-NIU-002"
    )


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
