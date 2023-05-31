ACCOUNT_BASE_URL = "https://account-fk.niu.com"
LOGIN_URI = "/v3/api/oauth2/token"
API_BASE_URL = "https://app-api-fk.niu.com"
MOTOR_BATTERY_API_URI = "/v3/motor_data/battery_info"
MOTOR_INDEX_API_URI = "/v5/scooter/motor_data/index_info"
MOTOINFO_LIST_API_URI = "/v5/scooter/list"
MOTOINFO_ALL_API_URI = "/motoinfo/overallTally"
TRACK_LIST_API_URI = "/v5/track/list/v2"
# FIRMWARE_BAS_URL = '/motorota/getfirmwareversion'

DOMAIN = "niu"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCOOTER_ID = "scooter_id"
CONF_AUTH = "conf_auth"
CONF_SENSORS = "sensors_selected"

DEFAULT_SCOOTER_ID = 0

SENSOR_TYPE_BAT = "BAT"
SENSOR_TYPE_MOTO = "MOTO"
SENSOR_TYPE_DIST = "DIST"
SENSOR_TYPE_OVERALL = "TOTAL"
SENSOR_TYPE_POS = "POSITION"
# SENSOR_TYPE_SYSTEM = 'SYSTEM'
SENSOR_TYPE_TRACK = "TRACK"

AVAILABLE_SENSORS = [
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


import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA

# Sensors schemas
from homeassistant.const import CONF_MONITORED_VARIABLES
import homeassistant.helpers.config_validation as cv

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
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
    ],
}
