"""
    Support for Niu Scooters by Marcel Westra.
    Asynchronous version implementation by Giovanni P. (@pikka97)
"""
from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .api import NiuApi
from .const import *

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    niu_auth = entry.data.get(CONF_AUTH, None)
    if niu_auth == None:
        _LOGGER.error(
            "The authenticator of your Niu integration is None.. can not setup the integration..."
        )
        return False

    username = niu_auth[CONF_USERNAME]
    password = niu_auth[CONF_PASSWORD]
    scooter_id = niu_auth[CONF_SCOOTER_ID]
    sensors_selected = niu_auth[CONF_SENSORS]

    api = NiuApi(username, password, scooter_id)
    await hass.async_add_executor_job(api.initApi)

    # add sensors
    devices = []
    for sensor in sensors_selected:
        if sensor != "LastTrackThumb":
            sensor_config = SENSOR_TYPES[sensor]
            devices.append(
                NiuSensor(
                    hass,
                    api,
                    sensor,
                    sensor_config[0],
                    sensor_config[1],
                    sensor_config[2],
                    sensor_config[3],
                    api.sensor_prefix,
                    sensor_config[4],
                    api.sn,
                    sensor_config[5],
                )
            )
        else:
            # Last Track Thumb sensor will be used as camera... now just skip it
            pass

    async_add_entities(devices)
    return True


class NiuSensor(Entity):
    def __init__(
        self,
        hass,
        api: NiuApi,
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
        self._hass = hass
        self._uom = uom
        self._api = api
        self._device_class = device_class
        self._id_name = id_name  # info field for parsing the URL
        self._sensor_grp = sensor_grp  # info field for choosing the right URL
        self._icon = icon
        self._state = None

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
    def device_info(self):
        device_name = "Niu E-scooter"
        return {
            "identifiers": {("niu", device_name)},
            "name": device_name,
            "manufacturer": "Niu",
            "model": 1.0,
        }

    @property
    def extra_state_attributes(self):
        if self._sensor_grp == SENSOR_TYPE_MOTO and self._id_name == "isConnected":
            return {
                "bmsId": self._api.getDataBat("bmsId"),
                "latitude": self._api.getDataPos("lat"),
                "longitude": self._api.getDataPos("lng"),
                "gsm": self._api.getDataMoto("gsm"),
                "gps": self._api.getDataMoto("gps"),
                "time": self._api.getDataDist("time"),
                "range": self._api.getDataMoto("estimatedMileage"),
                "battery": self._api.getDataBat("batteryCharging"),
                "battery_grade": self._api.getDataBat("gradeBattery"),
                "centre_ctrl_batt": self._api.getDataMoto("centreCtrlBattery"),
            }

    @Throttle(timedelta(seconds=30))
    async def async_update(self):
        if self._sensor_grp == SENSOR_TYPE_BAT:
            await self._hass.async_add_executor_job(self._api.updateBat)
            self._state = self._api.getDataBat(self._id_name)

        elif self._sensor_grp == SENSOR_TYPE_MOTO:
            await self._hass.async_add_executor_job(self._api.updateMoto)
            self._state = self._api.getDataMoto(self._id_name)

        elif self._sensor_grp == SENSOR_TYPE_POS:
            await self._hass.async_add_executor_job(self._api.updateMoto)
            self._state = self._api.getDataPos(self._id_name)

        elif self._sensor_grp == SENSOR_TYPE_DIST:
            await self._hass.async_add_executor_job(self._api.updateBat)
            self._state = self._api.getDataDist(self._id_name)

        elif self._sensor_grp == SENSOR_TYPE_OVERALL:
            await self._hass.async_add_executor_job(self._api.updateMotoInfo)
            self._state = self._api.getDataOverall(self._id_name)

        elif self._sensor_grp == SENSOR_TYPE_TRACK:
            await self._hass.async_add_executor_job(self._api.updateTrackInfo)
            self._state = self._api.getDataTrack(self._id_name)
