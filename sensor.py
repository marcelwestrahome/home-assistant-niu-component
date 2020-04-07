"""
@ Author      : Marcel Westra
@ Date        : 21/03/2020
@ Description : Nui Sensor - Monitor Nui Scooters. 
"""
VERSION = '0.0.1'

import json
import logging
import requests
from urllib.request import urlopen
from datetime import timedelta
from time import gmtime, strftime
import datetime

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_VARIABLES
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


#******************************************************************************************
# start to add to include file

API_BASE_URL = 'https://app-api-fk.niu.com'
ACCOUNT_BASE_URL = 'https://account-fk.niu.com'
BATINFO_BASE_URL = '/v3/motor_data/battery_info'
MOTOINDEX_BASE_URL = '/v3/motor_data/index_info'
MOTO_LIST_URL = '/motoinfo/list'
MOTOINFO_BASE_URL = '/motoinfo/overallTally'
FIRMWARE_BAS_URL = '/motorota/getfirmwareversion'


def get_token(email, password, cc):
    url = ACCOUNT_BASE_URL + '/appv2/login'
    data = {'account': email, 'countryCode': cc, 'password': password}
    try:
        r = requests.post(url, data=data)
    except BaseException as e:
        print (e)
        return False
    data = json.loads(r.content.decode())
    return data['data']['token']


def get_vehicles(token,id):

    url = API_BASE_URL + '/motoinfo/list'
    headers = {'token': token, 'Accept-Language': 'en-US'}
    try:
        r = requests.post(url, headers=headers, data=[])
    except ConnectionError as e:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    return data['data'][id]['sn']



def get_info(path, sn, token):
    url = API_BASE_URL + path

    params = {'sn': sn}
    headers = {'token': token, 'Accept-Language': 'en-US'}
    try:

        r = requests.get(url, headers=headers, params=params)

    except ConnectionError as e:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data['status'] != 0:
       return False
    return data

def post_info(path, sn, token):
    url = API_BASE_URL + path
    params = {}
    headers = {'token': token, 'Accept-Language': 'en-US'}
    try:
        r = requests.post(url, headers=headers, params=params, data={'sn':sn})
    except ConnectionError as e:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data['status'] != 0:
        return False
    return data

# end to add to include file
#*****************************************************************

DOMAIN = 'nui'
CONF_EMAIL = 'email'
CONF_PASSWORD = 'password'
CONF_COUNTRY = 'country'
CONF_ID = 'scooter_id'
CONF_NAME = 'name'

SENSOR_TYPE_BAT = 'BAT'
SENSOR_TYPE_MOTO = 'MOTO'
SENSOR_TYPE_DIST = 'DIST'
SENSOR_TYPE_OVERALL = 'TOTAL'
SENSOR_TYPE_POS = 'POSITION'
SENSOR_TYPE_SYSTEM = 'SYSTEM'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_COUNTRY): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=['BatteryCharge']): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(['BatteryCharge', 
                                                          'Isconnected', 
                                                          'TimesCharged', 
                                                          'temperatureDesc',
                                                          'Temperature',
                                                          'BatteryGrade',
                                                          'CurrentSpeed',
                                                          'IsConnected2',
                                                          'IsCharging',
                                                          'IsLocked',
                                                          'GSMSignal',
                                                          'GPSSignal',
                                                          'TimeLeft',
                                                          'EstimatedMileage',
                                                          'centreCtrlBatt',
                                                          'PosLat',
                                                          'PosLng',
                                                          'HDOP',
                                                          'Timestamp',
                                                          'Distance',
                                                          'RidingTime',
                                                          'totalMileage,'
                                                          'DaysInUse',
                                                          'LastUpdate'])])
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_TYPES = {
    'BatteryCharge': ['battery_charge', '%', 'mdi:battery', 'batteryCharging', SENSOR_TYPE_BAT],
    'Isconnected': ['is_connected', '', 'mdi:resistor', 'isConnected', SENSOR_TYPE_BAT],
    'TimesCharged': ['times_charged', 'x', 'mdi:numeric', 'chargedTimes', SENSOR_TYPE_BAT],
    'temperatureDesc': ['temp_descr', '', 'mdi:thermometer', 'temperatureDesc', SENSOR_TYPE_BAT],
    'Temperature': ['temperature', '°C', 'mdi:thermometer', 'temperature', SENSOR_TYPE_BAT],
    'BatteryGrade': ['battery_grade', '%', 'mdi:battery', 'gradeBattery', SENSOR_TYPE_BAT],
    'CurrentSpeed': ['current_speed',  '', 'mdi:speedometer', 'nowSpeed', SENSOR_TYPE_MOTO],
    'IsConnected2': ['is_connected2',  '', 'mdi:resistor', 'isConnected', SENSOR_TYPE_MOTO],
    'IsCharging': ['is_charging',  '', 'mdi:battery-charging-high', 'isCharging', SENSOR_TYPE_MOTO],
    'IsLocked': ['is_locked', '', 'mdi:lock', 'lockStatus', SENSOR_TYPE_MOTO],
    'GSMSignal': ['gsm_signal',  '', 'mdi:signal', 'gsm', SENSOR_TYPE_MOTO],
    'GPSSignal': ['gps_signal',  '', 'mdi:map-marker-multiple-outline', 'gps', SENSOR_TYPE_MOTO],
    'TimeLeft': ['time_left',  '', 'mdi:clock', 'leftTime', SENSOR_TYPE_MOTO],
    'EstimatedMileage': ['estimated_mileage',  'km', 'mdi:ray-start-arrow', 'estimatedMileage', SENSOR_TYPE_MOTO],
    'centreCtrlBatt': ['centre_ctrl_batt',  '', 'mdi:battery', 'centreCtrlBattery', SENSOR_TYPE_MOTO],
    'PosLat': ['pos_lat',  '', 'mdi:map-marker', 'lat', SENSOR_TYPE_POS],
    'PosLng': ['pos_lng',  '', 'mdi:map-marker', 'lng', SENSOR_TYPE_POS],
    'HDOP': ['hdp',  '', '', 'hdop', SENSOR_TYPE_MOTO],
    'Timestamp': ['time_stamp', '', 'mdi:clock', 'time', SENSOR_TYPE_DIST],
    'Distance': ['distance',  'km', 'mdi:ray-start-arrow', 'distance', SENSOR_TYPE_DIST],
    'RidingTime': ['riding_time', '', 'mdi:clock', 'ridingTime', SENSOR_TYPE_DIST],
    'totalMileage': ['total_mileage',  'km', 'mdi:ray-start-arrow', 'totalMileage', SENSOR_TYPE_OVERALL],
    'DaysInUse': ['bind_days_count',  '', 'mdi:calendar-month', 'bindDaysCount', SENSOR_TYPE_OVERALL],
    'LastUpdate': ['last_update',  '', 'mdi:calendar-month', 'LastUpdate', SENSOR_TYPE_SYSTEM]
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    
    #get config variables
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    country = config.get(CONF_COUNTRY)
    id_scooter = config.get(CONF_ID)
    sensor_prefix = config.get(CONF_NAME)

    #get token and unique scooter sn
    token = get_token(email, password, country)
    sn = get_vehicles(token,int(id_scooter))
    sensors = config.get(CONF_MONITORED_VARIABLES)
    
    #init data class
    data_bridge = NuiDataBridge(sn,token)

    #add sensors
    devices = []   
    for sensor in sensors:
        sensor_config = SENSOR_TYPES[sensor]
        devices.append(NuiSensor(data_bridge, sensor, sensor_config[0], sensor_config[1], sensor_config[2],  sensor_config[3],sensor_config[4], sensor_prefix))

    add_devices(devices)


class NuiDataBridge(object):

    def __init__(self, sn, token):
                
        self._dataBat = None
        self._dataMoto = None
        self._dataMotoInfo = None
        self._sn = sn
        self._token = token
        self._lastupdate = 'please turn on niu scooter (scooter does not send status after certain time locked)'
           
    def dataBat(self, id_field):
        return self._dataBat['data']['batteries']['compartmentA'][id_field]

    def dataMoto(self,id_field):
        return self._dataMoto['data'][id_field]

    def dataDist(self,id_field):
        return self._dataMoto['data']['lastTrack'][id_field]

    def dataPos(self, id_field):
        return self._dataMoto['data']['postion'][id_field]

    def dataOverall(self, id_field):
        return self._dataMotoInfo['data'][id_field]

    def dataSystem(self, id_field):
        return self._lastupdate

    @Throttle(timedelta(minutes=10))
    def update(self):

        data = get_info(BATINFO_BASE_URL,self._sn,self._token)

        #test to pass the niu bug of disconnected scooter
        if data['data']['batteries']['compartmentA']['batteryCharging'] != 0 :
            self._dataBat = get_info(BATINFO_BASE_URL,self._sn,self._token)
            self._lastupdate = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        else: 
            self._dataBat = None

        self._dataMoto = get_info(MOTOINDEX_BASE_URL, self._sn,self._token)
        self._dataMotoInfo = post_info(MOTOINFO_BASE_URL, self._sn,self._token)
           
        
       
        
class NuiSensor(Entity):

    def __init__(self, data_bridge, name,  sensor_id, uom, icon, id_name,sensor_grp, sensor_prefix):
        self._name = name
        self._property = name
        self._icon = icon
        self._uom = uom
        self._data_bridge = data_bridge
        self.entity_id = 'sensor.'+ sensor_prefix + sensor_id
        self._id_name = id_name
        self._state = '..'
        self._sensor_grp = sensor_grp
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
            return {'ScooterID' : self._data_bridge.dataBat('bmsId') }
       
    
    def update(self):
        self._data_bridge.update()
    
        if self._sensor_grp == SENSOR_TYPE_BAT:
            self._raw = self._data_bridge.dataBat(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_MOTO:
            self._raw = self._data_bridge.dataMoto(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_POS:
            self._raw = self._data_bridge.dataPos(self._id_name) 
        elif self._sensor_grp == SENSOR_TYPE_DIST:
            self._raw = self._data_bridge.dataDist(self._id_name) 
        elif self._sensor_grp == SENSOR_TYPE_OVERALL:
            self._raw = self._data_bridge.dataOverall(self._id_name) 
        elif self._sensor_grp == SENSOR_TYPE_SYSTEM:
            self._state = self._data_bridge.dataSystem(self._id_name)
        
        if self._raw is not None:
             self._state = self._raw

   