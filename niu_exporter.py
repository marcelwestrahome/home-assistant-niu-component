#!/usr/bin/env python3
#import os
#import requests
#import json
#from requests.exceptions import ConnectionError
import time
from prometheus_client import start_http_server
from prometheus_client import Counter, Gauge
from niu import get_token, get_vehicles, get_info, post_info
port_number = 8777

if __name__ == "__main__":
    token = get_token()
    sn = get_vehicles(token)
    data = get_info('/v3/motor_data/battery_info', sn, token)
    batteryInfo = data['data']['batteries']['compartmentA']
#    niu_bms_id = Gauge('niu_bms_id', 'ID of the Battery Management System')
    niu_battery_charge = Gauge('niu_battery_charge', 'Battery state of charge in percent')
    niu_times_charged = Gauge('niu_times_charged', 'number of times the battery has been charged')
    niu_temperature = Gauge('niu_temperature', 'Temperature at the battery in percent')
    niu_battery_grade = Gauge('niu_battery_grade', 'Battery Grade')
    niu_bindDaysCount = Gauge('niu_bindDaysCount', 'days the vehicle is connected to this account')
    niu_totalMileage = Gauge('niu_totalMileage', 'Total Mileage in km')
    # Start up the server to expose the metrics.
    start_http_server(port_number)
    # Generate some requests.
    print ('web server started')
    while True:
        try:
            data = get_info('/v3/motor_data/battery_info', sn, token)
            batteryInfo = data['data']['batteries']['compartmentA']
#            niu_bms_id.set(batteryInfo['bmsId'])
            niu_battery_charge.set(batteryInfo['batteryCharging'])
            niu_times_charged.set(batteryInfo['chargedTimes'])
            niu_temperature.set(batteryInfo['temperature'])
            niu_battery_grade.set(batteryInfo['gradeBattery'])
            overallTally = post_info('/motoinfo/overallTally', sn, token)
            niu_bindDaysCount.set(overallTally['data']['bindDaysCount'])
            niu_totalMileage.set(overallTally['data']['totalMileage'])
        except Exception as e:
            print("Caught Error")
            print(e)
        time.sleep(120)

"""
    print ('BMS-Id:        ', batteryInfo['bmsId'])
    print ('BatteryCharge: ', batteryInfo['batteryCharging'])
    print ('Is connected:  ', batteryInfo['isConnected'])
    print ('Times charged: ', batteryInfo['chargedTimes'])
    print ('Temperature:   ', batteryInfo['temperature'])
    print ('Battery Grade: ', batteryInfo['gradeBattery'])

    motorInfo = get_info('/v3/motor_data/index_info', sn, token)

    print ('Motor Info:')
    print ('exp. range:    ', motorInfo['data']['estimatedMileage'])
    print ('current speed: ', motorInfo['data']['nowSpeed'])
    print ('is connected:  ', motorInfo['data']['isConnected'])
    print ('is charging:   ', motorInfo['data']['isCharging'])
    print ('is locked:     ', motorInfo['data']['lockStatus'])
    print ('gsm signal:    ', motorInfo['data']['gsm'])
    print ('gps signal:    ', motorInfo['data']['gps'])
    print ('Time left:     ', motorInfo['data']['leftTime'])
    print ('centreCtrlBatt:', motorInfo['data']['centreCtrlBattery'])
    print ('Position lat:  ', motorInfo['data']['postion']['lat'])
    print ('Position lng:  ', motorInfo['data']['postion']['lng'])
    print ('Lastjkk Track:  ')
    print ('  Timestamp:   ', motorInfo['data']['lastTrack']['time'])
    print ('  Distance:    ', motorInfo['data']['lastTrack']['distance'])
    print ('  Riding Time: ', motorInfo['data']['lastTrack']['ridingTime'])
    print (motorInfo)
    {'trace': '成功', 'status': 0, 'desc': '成功', 'data': {'ss_protocol_ver': 2,
    'nowSpeed': 0, 'isAccOn': '', 'isConnected': True, 'infoTimestamp':
    1561015942946, 'leftTime': '17.0', 'isCharging': 0, 'hdop': 0, 'gsm': 24,
    'gps': 3, 'centreCtrlBattery': 100, 'gpsTimestamp': 1560976555998,
    'batteryDetail': True, 'lockStatus': 0, 'isFortificationOn': '',
    'batteries': {'compartmentA': {'batteryCharging': 49, 'bmsId':
    'BN1GPC2B40400386', 'isConnected': True, 'gradeBattery': '99'}},
    'time': 1561015942946, 'ss_online_sta': '1', 'lastTrack': {'time':
    1560976555998, 'distance': 7755, 'ridingTime': 1066},
    'postion': {'lng': 8.703397, 'lat': 50.105606}, 'estimatedMileage': 28}}

    # overallTally = post_info('/motoinfo/overallTally', sn, token)
    # print (overallTally)
    # {'desc': 'Success', 'status': 0, 'trace': 'Success', 'data': {'bindDaysCount': 66, 'totalMileage': 352}}
    batteryHealth = get_info('/v3/motor_data/battery_info/health', sn, token)
    # fand ich überwiegend als info nicht spannend
    print (batteryHealth)
    # {'desc': '成功', 'trace': '成功', 'data': {'isDoubleBattery': False,
    'batteries': {'compartmentA': {'healthRecords': [{'time': 1561017242842,
    'chargeCount': '10', 'name': '电池循环 * 10', 'color': '#878787',
    'result': '-1'}], 'faults': [], 'isConnected': True, 'gradeBattery': '99',
    'bmsId': 'BN1GPC2B40400386'}}}, 'status': 0}
    print ('is double batt:', batteryHealth['data']['isDoubleBattery'])
    # firmwareInfo = get_info('/motorota/getfirmwareversion', sn, token)
    # print (firmwareInfo)
    """
