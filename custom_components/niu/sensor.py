"""Support for Niu Scooters by Marcel Westra."""
from datetime import datetime, timedelta
import json
import logging
from time import gmtime, strftime

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_VARIABLES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

ACCOUNT_BASE_URL = "https://account-fk.niu.com"
LOGIN_URI = "/appv2/login"
API_BASE_URL = "https://app-api-fk.niu.com"
MOTOR_BATTERY_API_URI = "/v3/motor_data/battery_info"
MOTOR_INDEX_API_URI = "/v3/motor_data/index_info"
MOTOINFO_LIST_API_URI = "/motoinfo/list"
MOTOINFO_ALL_API_URI = "/motoinfo/overallTally"
TRACK_LIST_API_URI = "/v5/track/list/v2"
# FIRMWARE_BAS_URL = '/motorota/getfirmwareversion'

DOMAIN = "niu"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY = "country"
CONF_SCOOTER_ID = "scooter_id"

DEFAULT_SCOOTER_ID = 0

SENSOR_TYPE_BAT = "BAT"
SENSOR_TYPE_MOTO = "MOTO"
SENSOR_TYPE_DIST = "DIST"
SENSOR_TYPE_OVERALL = "TOTAL"
SENSOR_TYPE_POS = "POSITION"
# SENSOR_TYPE_SYSTEM = 'SYSTEM'
SENSOR_TYPE_TRACK = "TRACK"

# MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_COUNTRY): cv.positive_int,
        vol.Optional(CONF_SCOOTER_ID, default=DEFAULT_SCOOTER_ID): cv.positive_int,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["BatteryCharge"]): vol.All(
            cv.ensure_list,
            vol.Length(min=1),
            [
                vol.In(
                    [
                        "BatteryCharge",
                        "Isconnected",
                        "TimesCharged",
                        "temperatureDesc",
                        "Temperature",
                        "BatteryGrade",
                        "CurrentSpeed",
                        "ScooterConnected",
                        "IsCharging",
                        "IsLocked",
                        "TimeLeft",
                        "EstimatedMileage",
                        "centreCtrlBatt",
                        "HDOP",
                        "Longitude",
                        "Latitude",
                        "Distance",
                        "RidingTime",
                        "totalMileage",
                        "DaysInUse",
                        "LastTrackStartTime",
                        "LastTrackEndTime",
                        "LastTrackDistance",
                        "LastTrackAverageSpeed",
                        "LastTrackRidingtime",
                        "LastTrackThumb",
                    ]
                )
            ],
        ),
    }
)

SENSOR_TYPES = {
    "BatteryCharge": [
        "battery_charge",
        "%",
        "batteryCharging",
        SENSOR_TYPE_BAT,
        "battery",
        "mdi:battery-charging-50",
    ],
    "Isconnected": [
        "is_connected",
        "",
        "isConnected",
        SENSOR_TYPE_BAT,
        "connectivity",
        "mdi:connection",
    ],
    "TimesCharged": [
        "times_charged",
        "x",
        "chargedTimes",
        SENSOR_TYPE_BAT,
        "none",
        "mdi:battery-charging-wireless",
    ],
    "temperatureDesc": [
        "temp_descr",
        "",
        "temperatureDesc",
        SENSOR_TYPE_BAT,
        "none",
        "mdi:thermometer-alert",
    ],
    "Temperature": [
        "temperature",
        "°C",
        "temperature",
        SENSOR_TYPE_BAT,
        "temperature",
        "mdi:thermometer",
    ],
    "BatteryGrade": [
        "battery_grade",
        "%",
        "gradeBattery",
        SENSOR_TYPE_BAT,
        "battery",
        "mdi:car-battery",
    ],
    "CurrentSpeed": [
        "current_speed",
        "km/h",
        "nowSpeed",
        SENSOR_TYPE_MOTO,
        "none",
        "mdi:speedometer",
    ],
    "ScooterConnected": [
        "scooter_connected",
        "",
        "isConnected",
        SENSOR_TYPE_MOTO,
        "connectivity",
        "mdi:motorbike-electric",
    ],
    "IsCharging": [
        "is_charging",
        "",
        "isCharging",
        SENSOR_TYPE_MOTO,
        "power",
        "mdi:battery-charging",
    ],
    "IsLocked": ["is_locked", "", "lockStatus", SENSOR_TYPE_MOTO, "lock", "mdi:lock"],
    "TimeLeft": [
        "time_left",
        "h",
        "leftTime",
        SENSOR_TYPE_MOTO,
        "none",
        "mdi:av-timer",
    ],
    "EstimatedMileage": [
        "estimated_mileage",
        "km",
        "estimatedMileage",
        SENSOR_TYPE_MOTO,
        "none",
        "mdi:map-marker-distance",
    ],
    "centreCtrlBatt": [
        "centre_ctrl_batt",
        "%",
        "centreCtrlBattery",
        SENSOR_TYPE_MOTO,
        "battery",
        "mdi:car-cruise-control",
    ],
    "HDOP": ["hdp", "", "hdop", SENSOR_TYPE_MOTO, "none", "mdi:map-marker"],
    "Longitude": ["long", "", "lng", SENSOR_TYPE_POS, "none", "mdi:map-marker"],
    "Latitude": ["lat", "", "lat", SENSOR_TYPE_POS, "none", "mdi:map-marker"],
    "Distance": [
        "distance",
        "m",
        "distance",
        SENSOR_TYPE_DIST,
        "none",
        "mdi:map-marker-distance",
    ],
    "RidingTime": [
        "riding_time",
        "s",
        "ridingTime",
        SENSOR_TYPE_DIST,
        "none",
        "mdi:map-clock",
    ],
    "totalMileage": [
        "total_mileage",
        "km",
        "totalMileage",
        SENSOR_TYPE_OVERALL,
        "none",
        "mdi:map-marker-distance",
    ],
    "DaysInUse": [
        "bind_days_count",
        "days",
        "bindDaysCount",
        SENSOR_TYPE_OVERALL,
        "none",
        "mdi:calendar-today",
    ],
    "LastTrackStartTime": [
        "last_track_start_time",
        "",
        "startTime",
        SENSOR_TYPE_TRACK,
        "none",
        "mdi:clock-start",
    ],
    "LastTrackEndTime": [
        "last_track_end_time",
        "",
        "endTime",
        SENSOR_TYPE_TRACK,
        "none",
        "mdi:clock-end",
    ],
    "LastTrackDistance": [
        "last_track_distance",
        "m",
        "distance",
        SENSOR_TYPE_TRACK,
        "none",
        "mdi:map-marker-distance",
    ],
    "LastTrackAverageSpeed": [
        "last_track_average_speed",
        "km/h",
        "avespeed",
        SENSOR_TYPE_TRACK,
        "none",
        "mdi:speedometer",
    ],
    "LastTrackRidingtime": [
        "last_track_riding_time",
        "",
        "ridingtime",
        SENSOR_TYPE_TRACK,
        "none",
        "mdi:timelapse",
    ],
    "LastTrackThumb": [
        "last_track_thumb",
        "",
        "track_thumb",
        SENSOR_TYPE_TRACK,
        "none",
        "mdi:map",
    ]
    #   'Config' : [sensor_id, uom, id_name, sensor_grp, device_class, icon]
}
# NiuSensor(data_bridge, sensor, sensor_config[0], sensor_config[1], sensor_config[2],sensor_config[3], sensor_prefix, sensor_config[4], sn, sensor_config[5] ))
# NiuSensor(data_bridge, name,  sensor_id, uom, id_name,sensor_grp, sensor_prefix, device_class, sn, icon)


def get_token(username, password, cc):
    url = ACCOUNT_BASE_URL + LOGIN_URI
    data = {"account": username, "countryCode": cc, "password": password}
    try:
        r = requests.post(url, data=data)
    except BaseException as e:
        print(e)
        return False
    data = json.loads(r.content.decode())
    return data["data"]["token"]


def get_vehicles_info(path, token):

    url = API_BASE_URL + path
    headers = {"token": token, "Accept-Language": "en-US"}
    try:
        r = requests.post(url, headers=headers, data=[])
    except ConnectionError:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    return data


def get_info(path, sn, token):
    url = API_BASE_URL + path

    params = {"sn": sn}
    headers = {"token": token, "Accept-Language": "en-US"}
    try:

        r = requests.get(url, headers=headers, params=params)

    except ConnectionError:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data["status"] != 0:
        return False
    return data


def post_info(path, sn, token):
    url = API_BASE_URL + path
    params = {}
    headers = {"token": token, "Accept-Language": "en-US"}
    try:
        r = requests.post(url, headers=headers, params=params, data={"sn": sn})
    except ConnectionError:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data["status"] != 0:
        return False
    return data


def post_info_track(path, sn, token):
    url = API_BASE_URL + path
    params = {}
    headers = {
        "token": token,
        "Accept-Language": "en-US",
        "User-Agent": "manager/1.0.0 (identifier);clientIdentifier=identifier",
    }
    try:
        r = requests.post(
            url,
            headers=headers,
            params=params,
            json={"index": "0", "pagesize": 10, "sn": sn},
        )
    except ConnectionError:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data["status"] != 0:
        return False
    return data


def setup_platform(hass, config, add_devices, discovery_info=None):

    # get config variables
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    country = config.get(CONF_COUNTRY)
    scooter_id = config.get(CONF_SCOOTER_ID)
    api_uri = MOTOINFO_LIST_API_URI

    # get token and unique scooter sn
    token = get_token(username, password, country)
    sn = get_vehicles_info(api_uri, token)["data"][scooter_id]["sn"]
    sensor_prefix = get_vehicles_info(api_uri, token)["data"][scooter_id]["name"]

    sensors = config.get(CONF_MONITORED_VARIABLES)

    # init data class
    data_bridge = NiuDataBridge(sn, token)
    data_bridge.updateBat()
    data_bridge.updateMoto()
    data_bridge.updateMotoInfo()
    data_bridge.updateTrackInfo()

    # add sensors
    devices = []
    for sensor in sensors:
        sensor_config = SENSOR_TYPES[sensor]
        devices.append(
            NiuSensor(
                data_bridge,
                sensor,
                sensor_config[0],
                sensor_config[1],
                sensor_config[2],
                sensor_config[3],
                sensor_prefix,
                sensor_config[4],
                sn,
                sensor_config[5],
            )
        )
    add_devices(devices)


class NiuDataBridge(object):
    def __init__(self, sn, token):

        self._dataBat = None
        self._dataMoto = None
        self._dataMotoInfo = None
        self._dataTrackInfo = None
        self._sn = sn
        self._token = token

    def dataBat(self, id_field):
        return self._dataBat["data"]["batteries"]["compartmentA"][id_field]

    def dataMoto(self, id_field):
        return self._dataMoto["data"][id_field]

    def dataDist(self, id_field):
        return self._dataMoto["data"]["lastTrack"][id_field]

    def dataPos(self, id_field):
        return self._dataMoto["data"]["postion"][id_field]

    def dataOverall(self, id_field):
        return self._dataMotoInfo["data"][id_field]

    def dataTrack(self, id_field):
        if id_field == "startTime" or id_field == "endTime":
            return datetime.fromtimestamp(
                (self._dataTrackInfo["data"][0][id_field]) / 1000
            ).strftime("%Y-%m-%d %H:%M:%S")
        if id_field == "ridingtime":
            return strftime(
                "%H:%M:%S", gmtime(self._dataTrackInfo["data"][0][id_field])
            )
        if id_field == "track_thumb":
            thumburl = self._dataTrackInfo["data"][0][id_field].replace(
                "app-api.niucache.com", "app-api-fk.niu.com"
            )
            return thumburl.replace("/track/thumb/", "/track/overseas/thumb/")
        return self._dataTrackInfo["data"][0][id_field]

    @Throttle(timedelta(seconds=1))
    def updateBat(self):
        self._dataBat = get_info(MOTOR_BATTERY_API_URI, self._sn, self._token)

    @Throttle(timedelta(seconds=1))
    def updateMoto(self):
        self._dataMoto = get_info(MOTOR_INDEX_API_URI, self._sn, self._token)

    @Throttle(timedelta(seconds=1))
    def updateMotoInfo(self):
        self._dataMotoInfo = post_info(MOTOINFO_ALL_API_URI, self._sn, self._token)

    @Throttle(timedelta(seconds=1))
    def updateTrackInfo(self):
        self._dataTrackInfo = post_info_track(TRACK_LIST_API_URI, self._sn, self._token)


class NiuSensor(Entity):
    def __init__(
        self,
        data_bridge,
        name,
        sensor_id,
        uom,
        id_name,
        sensor_grp,
        sensor_prefix,
        device_class,
        sn,
        icon,
    ):
        self._unique_id = "sensor.niu_scooter_" + sn + "_" + sensor_id
        self._name = (
            "NIU Scooter " + sensor_prefix + " " + name
        )  # Scooter name as sensor prefix
        self._uom = uom
        self._data_bridge = data_bridge
        self._device_class = device_class
        self._id_name = id_name  # info field for parsing the URL
        self._sensor_grp = sensor_grp  # info field for choosing the right URL
        self._icon = icon

        # first init
        if self._sensor_grp == SENSOR_TYPE_BAT:
            self._state = self._data_bridge.dataBat(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_MOTO:
            self._state = self._data_bridge.dataMoto(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_POS:
            self._state = self._data_bridge.dataPos(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_DIST:
            self._state = self._data_bridge.dataDist(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_OVERALL:
            self._state = self._data_bridge.dataOverall(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_TRACK:
            self._state = self._data_bridge.dataTrack(self._id_name)

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        return self._name

    @property
    def unit_of_measurement(self):
        return self._uom

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        return self._state

    @property
    def device_class(self):
        return self._device_class

    @property
    def extra_state_attributes(self):
        if self._sensor_grp == SENSOR_TYPE_MOTO and self._id_name == "isConnected":
            return {
                "bmsId": self._data_bridge.dataBat("bmsId"),
                "latitude": self._data_bridge.dataPos("lat"),
                "longitude": self._data_bridge.dataPos("lng"),
                "gsm": self._data_bridge.dataMoto("gsm"),
                "gps": self._data_bridge.dataMoto("gps"),
                "time": self._data_bridge.dataDist("time"),
                "range": self._data_bridge.dataMoto("estimatedMileage"),
                "battery": self._data_bridge.dataBat("batteryCharging"),
                "battery_grade": self._data_bridge.dataBat("gradeBattery"),
                "centre_ctrl_batt": self._data_bridge.dataMoto("centreCtrlBattery"),
            }

    def update(self):
        if self._sensor_grp == SENSOR_TYPE_BAT:
            self._data_bridge.updateBat()
            self._state = self._data_bridge.dataBat(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_MOTO:
            self._data_bridge.updateMoto()
            self._state = self._data_bridge.dataMoto(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_POS:
            self._data_bridge.updateMoto()
            self._state = self._data_bridge.dataPos(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_DIST:
            self._data_bridge.updateMoto()
            self._state = self._data_bridge.dataDist(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_OVERALL:
            self._data_bridge.updateMotoInfo()
            self._state = self._data_bridge.dataOverall(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_TRACK:
            self._data_bridge.updateTrackInfo()
            self._state = self._data_bridge.dataTrack(self._id_name)
