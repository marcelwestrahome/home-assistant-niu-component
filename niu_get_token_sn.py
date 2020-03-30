#!/usr/bin/env python3
from niu import get_token, get_vehicles, get_info

if __name__ == "__main__":
    token = get_token()
    sn = get_vehicles(token)
    print ('Token:         ', token)
    print ('Serien-Nummer: ', sn)
