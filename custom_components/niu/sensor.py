"""Sensor entities for NIU scooters."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from .const import (
    CONF_AUTH,
    CONF_SENSORS,
    DOMAIN,
    SENSOR_TYPE_BAT,
    SENSOR_TYPE_BAT2,
    SENSOR_TYPE_DIST,
    SENSOR_TYPE_MOTO,
    SENSOR_TYPE_OVERALL,
    SENSOR_TYPE_POS,
    SENSOR_TYPE_TRACK,
    SENSOR_TYPES,
)
from .coordinator import NiuDataUpdateCoordinator
from .entity import NiuCoordinatorEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up NIU sensors from a config entry."""
    coordinator: NiuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors_selected = entry.data[CONF_AUTH][CONF_SENSORS]

    entities = []
    for sensor in sensors_selected:
        if sensor == "LastTrackThumb" or sensor not in SENSOR_TYPES:
            continue
        sensor_config = SENSOR_TYPES[sensor]
        entities.append(
            NiuSensor(
                coordinator,
                sensor,
                sensor_config[0],
                sensor_config[1],
                sensor_config[2],
                sensor_config[3],
                sensor_config[4],
                sensor_config[5],
            )
        )

    async_add_entities(entities)


class NiuSensor(NiuCoordinatorEntity, SensorEntity):
    """A NIU sensor backed by the config entry's shared coordinator."""

    def __init__(
        self,
        coordinator: NiuDataUpdateCoordinator,
        name: str,
        sensor_id: str,
        unit: str,
        data_field: str,
        sensor_group: str,
        device_class: str,
        icon: str,
    ) -> None:
        NiuCoordinatorEntity.__init__(self, coordinator)
        api = coordinator.data
        self._api = api
        self._data_field = data_field
        self._sensor_group = sensor_group
        self._attr_unique_id = f"sensor.niu_scooter_{api.sn}_{sensor_id}"
        self._attr_name = f"NIU Scooter {api.sensor_prefix} {name}"
        self._attr_native_unit_of_measurement = unit or None
        self._attr_device_class = device_class if device_class != "none" else None
        self._attr_icon = icon

    @property
    def native_value(self):
        """Return a value from the coordinator's cached API response."""
        if self._sensor_group == SENSOR_TYPE_BAT:
            return self._api.getDataBatA(self._data_field)
        if self._sensor_group == SENSOR_TYPE_BAT2:
            return self._api.getDataBatB(self._data_field)
        if self._sensor_group == SENSOR_TYPE_MOTO:
            return self._api.getDataMoto(self._data_field)
        if self._sensor_group == SENSOR_TYPE_POS:
            return self._api.getDataPos(self._data_field)
        if self._sensor_group == SENSOR_TYPE_DIST:
            return self._api.getDataDist(self._data_field)
        if self._sensor_group == SENSOR_TYPE_OVERALL:
            return self._api.getDataOverall(self._data_field)
        if self._sensor_group == SENSOR_TYPE_TRACK:
            return self._api.getDataTrack(self._data_field)
        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return diagnostic attributes for the connection sensor."""
        if self._sensor_group != SENSOR_TYPE_MOTO or self._data_field != "isConnected":
            return None

        attributes = {
            "bmsId_a": self._api.getDataBatA("bmsId"),
            "latitude": self._api.getDataPos("lat"),
            "longitude": self._api.getDataPos("lng"),
            "gsm": self._api.getDataMoto("gsm"),
            "gps": self._api.getDataMoto("gps"),
            "time": self._api.getDataDist("time"),
            "range": self._api.getDataMoto("estimatedMileage"),
            "battery_a": self._api.getDataBatA("batteryCharging"),
            "battery_grade_a": self._api.getDataBatA("gradeBattery"),
            "centre_ctrl_batt": self._api.getDataMoto("centreCtrlBattery"),
        }
        if self._api.hasSecondBattery():
            attributes.update(
                {
                    "bmsId_b": self._api.getDataBatB("bmsId"),
                    "battery_b": self._api.getDataBatB("batteryCharging"),
                    "battery_grade_b": self._api.getDataBatB("gradeBattery"),
                }
            )
        return attributes
