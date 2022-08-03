# niu

This is a custom component for Home Assistant to integrate your Niu Scooter.

## Install

You can install this custom component by adding this repository ([https://github.com/marcelwestrahome/home-assistant-niu-component](https://github.com/marcelwestrahome/home-assistant-niu-component)) to [HACS](https://hacs.xyz/) in the settings menu of HACS first. You will find the custom component in the integration menu afterwards, look for 'Niu Scooter Integration'. Alternatively, you can install it manually by copying the `custom_components` folder to your Home Assistant configuration folder.

## Setup

```yaml
# configuration.yaml

sensor:
  - platform: niu
    username: user@example.com
    password: mysecretpassword
    country: 49
    scooter_id: 0
    monitored_variables:
      - BatteryCharge          # Battery
      - Isconnected            # Battery
      - TimesCharged           # Battery
      - temperatureDesc        # Battery
      - Temperature            # Battery
      - BatteryGrade           # Battery
      - CurrentSpeed           # Moto
      - ScooterConnected       # Moto (has attributes lon. lat. for plotting on a map)
      - IsCharging             # Moto
      - IsLocked               # Moto
      - TimeLeft               # Moto
      - EstimatedMileage       # Moto
      - centreCtrlBatt         # Moto
      - HDOP                   # Moto
      - Longitude              # Moto
      - Latitude               # Moto
      - totalMileage           # OverAll
      - DaysInUse              # OverAll
      - Distance               # Distance
      - RidingTime             # Distance
      - LastTrackStartTime     # LastTrack
      - LastTrackEndTime       # LastTrack
      - LastTrackDistance      # LastTrack
      - LastTrackAverageSpeed  # LastTrack
      - LastTrackRidingtime    # LastTrack
      - LastTrackThumb         # LastTrack

```

Configuration variables:
- **username** (*Required*): EMail address or mobile phone number or username.
- **password** (*Required*): Niu Account password.
- **country** (*Required*): Telephone country count without leading zeros or + sign, e.g. 49 instead of 0049 or +49.
- **scooter_id** (*Optional*): The `scooter_id` to monitor. Defaults to 0.

If you own multiple scooters just add the niu sensor platform multiple times and increase the `scooter_id`.

## Known bugs

~~At this moment the NIU sport plus has a bug, at least this type scooter stops after a certain time updating. When this happen, component will show the last updated values. With a restart of your your HA, you need to turn on your scooter for a short time to see all sensor values.
Niu promises to solve this issue with a new firmware.~~

The known bug that's causing the updates to stop is fixed by Niu in the scooters firmware v3 (`TRA01E18`). This update has to be manually installed at an authorized dealer (so no automagical OTA install). @rmettes reported this firmware as stable.

I recieved new firmware for my scooter (TRA01E23). component will alsways show the new updated data. 

##
Component works also for KQ13, however this has only a bluetooth interface, so your need to be connected (not all sensors are working)

## Roadmap

Some day this component shall become an official HA integration. Until then just use this custom component.

