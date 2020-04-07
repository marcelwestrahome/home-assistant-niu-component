
import json
import requests
from urllib.request import urlopen

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