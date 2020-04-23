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


def get_vehicles_info(token):

    url = API_BASE_URL + '/motoinfo/list'
    headers = {'token': token, 'Accept-Language': 'en-US'}
    try:
        r = requests.post(url, headers=headers, data=[])
    except ConnectionError as e:
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    return data



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

#MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

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
                                                          'ScooterConnected',
                                                          'IsCharging',
                                                          'IsLocked',
                                                          'TimeLeft',
                                                          'EstimatedMileage',
                                                          'centreCtrlBatt',
                                                          'HDOP',
                                                          'Distance',
                                                          'RidingTime',
                                                          'totalMileage',
                                                          'DaysInUse' ])])
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_TYPES = {
    'BatteryCharge': ['battery_charge', '%', 'batteryCharging', SENSOR_TYPE_BAT,'battery'],
    'Isconnected': ['is_connected', '', 'isConnected', SENSOR_TYPE_BAT,'connectivity'],
    'TimesCharged': ['times_charged', 'x', 'chargedTimes', SENSOR_TYPE_BAT,'none'],
    'temperatureDesc': ['temp_descr', '', 'temperatureDesc', SENSOR_TYPE_BAT,'none'],
    'Temperature': ['temperature', '°C', 'temperature', SENSOR_TYPE_BAT,'temperature'],
    'BatteryGrade': ['battery_grade', '%', 'gradeBattery', SENSOR_TYPE_BAT,'battery'],
    'CurrentSpeed': ['current_speed',  'km/h', 'nowSpeed', SENSOR_TYPE_MOTO,'none'],
    'ScooterConnected': ['scooter_connected', '', 'isConnected', SENSOR_TYPE_MOTO,'connectivity'],
    'IsCharging': ['is_charging', '', 'isCharging', SENSOR_TYPE_MOTO,'power'],
    'IsLocked': ['is_locked', '', 'lockStatus', SENSOR_TYPE_MOTO,'lock'],
    'TimeLeft': ['time_left',  '','leftTime', SENSOR_TYPE_MOTO,'none'],
    'EstimatedMileage': ['estimated_mileage', 'km', 'estimatedMileage', SENSOR_TYPE_MOTO,'none'],
    'centreCtrlBatt': ['centre_ctrl_batt', '', 'centreCtrlBattery', SENSOR_TYPE_MOTO,'none'],
    'HDOP': ['hdp',  '', 'hdop', SENSOR_TYPE_MOTO,'none'],
    'Distance': ['distance', 'km', 'distance', SENSOR_TYPE_DIST,'none'],
    'RidingTime': ['riding_time', '','ridingTime', SENSOR_TYPE_DIST,'none'],
    'totalMileage': ['total_mileage', 'km', 'totalMileage', SENSOR_TYPE_OVERALL,'none'],
    'DaysInUse': ['bind_days_count', 'days', 'bindDaysCount', SENSOR_TYPE_OVERALL,'none'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    
    #get config variables
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    country = config.get(CONF_COUNTRY)
    id_scooter = int(config.get(CONF_ID))
    #sensor_prefix = config.get(CONF_NAME)

    #get token and unique scooter sn
    token = get_token(email, password, country)
    sn = get_vehicles_info(token)['data'][id_scooter]['sn']
    sensor_prefix = get_vehicles_info(token)['data'][id_scooter]['name']
    sensors = config.get(CONF_MONITORED_VARIABLES)
    
    #init data class
    data_bridge = NuiDataBridge(sn,token)
    data_bridge.updateBat()
    data_bridge.updateMoto()
    data_bridge.updateMotoInfo()

    #add sensors
    devices = []   
    for sensor in sensors:
        sensor_config = SENSOR_TYPES[sensor]
        devices.append(NuiSensor(data_bridge, sensor, sensor_config[0], sensor_config[1], sensor_config[2],sensor_config[3], sensor_prefix, sensor_config[4] ))
    add_devices(devices)


class NuiDataBridge(object):

    def __init__(self, sn, token):

        self._dataBat = None
        self._dataMoto = None
        self._dataMotoInfo = None
        self._sn = sn
        self._token = token
     
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

  
    @Throttle(timedelta(seconds=1))
    def updateBat(self):
        self._dataBat = get_info(BATINFO_BASE_URL,self._sn,self._token)

    @Throttle(timedelta(seconds=1))
    def updateMoto(self):
        self._dataMoto = get_info(MOTOINDEX_BASE_URL, self._sn,self._token)

    @Throttle(timedelta(seconds=1))
    def updateMotoInfo(self):
        self._dataMotoInfo = post_info(MOTOINFO_BASE_URL, self._sn,self._token)

class NuiSensor(Entity):

    def __init__(self, data_bridge, name,  sensor_id, uom, id_name,sensor_grp, sensor_prefix, device_class):
        self._name = 'NIU Scooter ' + sensor_prefix + ' ' + name
        self._uom = uom
        self._data_bridge = data_bridge
        self._entity_id = 'sensor.niu_scooter_'+ sensor_prefix + '_' + sensor_id
        self._device_class = device_class
        self._id_name = id_name  #info field for parsing the URL
        self._sensor_grp = sensor_grp #info field for choosing the right URL
    
    #first init
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


    @property
    def name(self):
        return self._name

    @property
    def unit_of_measurement(self):
        return self._uom
     
    @property
    def entity_id(self):
        return self._entity_id
 
    @property
    def state(self):
        return self._state

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_attributes(self):
        if  self._sensor_grp == SENSOR_TYPE_MOTO and self._id_name =='isConnected':
            return {'bmsId' : self._data_bridge.dataBat('bmsId'),
                    'latitude' : self._data_bridge.dataPos('lat'),
                    'longitude': self._data_bridge.dataPos('lng'),
                    'gsm': self._data_bridge.dataMoto('gsm'),
                    'gps': self._data_bridge.dataMoto('gps'),
                    'time': self._data_bridge.dataDist('time'),
            }


    def update(self):
        if self._sensor_grp == SENSOR_TYPE_BAT:
            self._data_bridge.updateBat()
            if not (self._id_name == 'batteryCharging' or self._id_name == 'temperature') and self._data_bridge.dataBat('batteryCharging') == 0:
                self._state = self._data_bridge.dataBat(self._id_name)
        elif self._sensor_grp == SENSOR_TYPE_MOTO:
            self._data_bridge.updateMoto()
            if not (self._id_name == 'estimatedMileage' or self._id_name == 'leftTime') and self._data_bridge.dataMoto('estimatedMileage') == 0:
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
           
 

