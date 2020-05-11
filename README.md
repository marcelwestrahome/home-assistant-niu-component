# niu

Home assistant niu sensor component to read the parameters of your scooter
for more scooters just add the components again with increasing the scooter id
scooter id 0 (one scooter)
scooter id 1 (two scooters)
etc

USername and password are the credentials of the niu app.

At this moment the NIU sport plus ahas a bug, at least this type scooter stops after a certain time updating.
When this happen, component will show the last updated values.
Niu promises with a new firmware to solve this problem.


Installation:

copy "__init__.py, manifest.json. sensor.py" to custom_components\niu directory

add the following to your configuration file and fill in your email address, password and country

restart home assistant

sensor:
  - platform: niu
    email: ##your email address##
    password: ##your password##
    country : ##your country##
    scooter_id : '0'
    monitored_variables:  
    - BatteryCharge
    - Isconnected 
    - TimesCharged 
    - temperatureDesc
    - Temperature
    - BatteryGrade
    - CurrentSpeed
    - ScooterConnected
    - IsCharging
    - IsLocked
    - TimeLeft
    - EstimatedMileage
    - centreCtrlBatt
    - HDOP
    - Distance
    - RidingTime
    - totalMileage
    - DaysInUse
