"""
@ Author      : Marcel Westra
@ Date        : 21/03/2020
@ Description : Nui Sensor - Monitor Nui Scooters. 
"""
VERSION = '0.0.1'

import json
import logging
from datetime import timedelta
from urllib.request import urlopen

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_VARIABLES
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DOMAIN = 'nui'
CONF_HOST = "host"
API_BASE_URL = 'https://app-api-fk.niu.com'
sn = 'MB2L3TE3525GMC8K'
token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyaWQiOiI1ZDk4YTI0OWE0YTQ1ZmQzNTg0MjgwMWQiLCJsb2dpbmlkIjoiIiwidiI6MSwiaWF0IjoxNTg0ODIxMTQ0LCJleHAiOjE1OTI1OTcxNDR9.W23dv18KbHUWqMk_v1r4ez5GmqarH1MzMOTxc6CSEhs'

SENSOR_PREFIX = 'nui_'
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=['bat', 'count']): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(['id', 'bat', 'connected', 'count', 'temp', 'trade'])])
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_TYPES = {
    'id': ['Current Power usage', 'current_power_usage', 'W', 'mdi:flash', 'energy.png'],
    'bat': ['Net Power usage', 'net_power_meter', 'kWh', 'mdi:gauge', 'electric-meter.png'],
    'connected': ['Power Meter Low', 'power_meter_low', 'kWh', 'mdi:gauge', 'energy.png'],
    'count': ['Power Meter High', 'power_meter_high', 'kWh', 'mdi:gauge', 'energy.png'],
    'temp': ['Power Delivery Low', 'power_delivery_low', 'kWh', 'mdi:gauge', 'energy.png'],
    'grade': ['Power Delivery High', 'power_delivery_high', 'kWh', 'mdi:gauge', 'energy.png']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    host = config.get(CONF_HOST)
    sensors = config.get(CONF_MONITORED_VARIABLES)
    data_bridge = NuiDataBridge(host)

    devices = []
    for sensor in sensors:
        sensor_config = SENSOR_TYPES[sensor]
        devices.append(NuiSensor(data_bridge, sensor_config[0], sensor, sensor_config[1], sensor_config[2], sensor_config[3], sensor_config[4]))

    add_devices(devices)


class NuiDataBridge(object):

    def __init__(self, host):
        params = {'sn': sn}
        headers = {'token': token, 'Accept-Language': 'en-US'}
        self._url = 'API_BASE_URL' + '/v3/motor_data/battery_info'
        self._data = None

    def data(self):
        return self._data

    @Throttle(timedelta(seconds=1))
    def update(self):
        r = requests.get(self._url, headers=headers, params=params)
        self._data = json.loads(r.content.decode())
        

class NuiSensor(Entity):

    def __init__(self, data_bridge, name, prpt, sensor_id, uom, icon, image_uri):
        self._state = None
        self._name = name
        self._property = prpt
        self._icon = icon
        #self._image = image_uri
        self._uom = uom
        self._data_bridge = data_bridge
        self.entity_id = 'sensor.' + SENSOR_PREFIX + sensor_id
        self._raw = None

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._uom

    @property
    def state(self):
        return self._state

    @property
    def state_attributes(self):
        if self._raw is not None:
            return {
                'timestamp': self._raw['tm']
            }

    def update(self):
        self._data_bridge.update()
        self._raw = self._data_bridge.data()
        if self._raw is not None:
            self._state = self._raw[self._property]
