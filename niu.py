#!/usr/bin/env python3
# -*- coding: utf-8 -*
import os
import requests
import json
from requests.exceptions import ConnectionError
# import time
# from prometheus_client import start_http_server
# from prometheus_client import Counter, Gauge
#https://account-fk.niu.com/login

API_BASE_URL = 'https://app-api-fk.niu.com'
ACCOUNT_BASE_URL = 'https://account-fk.niu.com'
NIU_EMAIL = 'marcel_westra@hotmail.com'
NIU_PASSWORD = 'TEmI3299VihW9Wv5'
NIU_COUNTRYCODE = '31'


def get_token(email=NIU_EMAIL, password=NIU_PASSWORD, cc=NIU_COUNTRYCODE):
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
        print("Caught Error")
        print(e)
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    return data['data'][id]['sn']
# übergebe nur die erste Seriennr. zu erweitern,
# wenn man mehr als 1 Roller mit dem Account verbunden hat


def get_info(path, sn, token):
    url = API_BASE_URL + path
#    print (url)
    params = {'sn': sn}
    headers = {'token': token, 'Accept-Language': 'en-US'}
    try:
        print(url)
        print(headers)
        print(params)
        r = requests.get(url, headers=headers, params=params)
    #    print (r.content)
    #    print (r.status_code)
    except ConnectionError as e:
        print("Caught Error")
        print(e)
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data['status'] != 0:
       return False
#    data = data['data']['batteries']['compartmentA']
#    del data['items']
    return data


def post_info(path, sn, token):
    url = API_BASE_URL + path
#    print (url)
    params = {}
    headers = {'token': token, 'Accept-Language': 'en-US'}
    try:
        r = requests.post(url, headers=headers, params=params, data={'sn':sn})
#        print (r.content)
#        print (r.status_code)
    except ConnectionError as e:
        print("Caught Error")
        print(e)
        return False
    if r.status_code != 200:
        return False
    data = json.loads(r.content.decode())
    if data['status'] != 0:
        return False
#    data = data['data']['batteries']['compartmentA']
#    del data['items']
    return data

def printinfo(token):

    data = get_info('/v3/motor_data/battery_info', sn, token)
    
    batteryInfo = data['data']['batteries']['compartmentA']
    print ('Battery Info:')
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
    print ('HDOP:          ', motorInfo['data']['hdop'])
    if (len(motorInfo['data']['lastTrack'])) != 0:
        print ('Last Track:  ')
        print ('  Timestamp:   ', motorInfo['data']['lastTrack']['time'])
        print ('  Distance:    ', motorInfo['data']['lastTrack']['distance'])
        print ('  Riding Time: ', motorInfo['data']['lastTrack']['ridingTime'])

    overallTally = post_info('/motoinfo/overallTally', sn, token)
    print ('Total km:      ', overallTally['data']['totalMileage'])
    print ('Total km since:', overallTally['data']['bindDaysCount'], 'days')

    batteryHealth = get_info('/v3/motor_data/battery_info/health', sn, token)
    print ('is double batt:', batteryHealth['data']['isDoubleBattery'])
    
    #firmwareInfo = get_info('/motorota/getfirmwareversion', sn, token)
    #print (firmwareInfo)
    print ("\n \n")

if __name__ == "__main__":
    token = get_token()
    print(token)
    sn = get_vehicles(token,0)
    printinfo(token)
    sn = get_vehicles(token,1)
    printinfo(token)
