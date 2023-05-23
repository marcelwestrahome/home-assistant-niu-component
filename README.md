# Niu E-scooter Home Assistant integration

This is a custom component for Home Assistant to integrate your Niu Scooter.

Now this integration is _asynchronous_ and it is easy installable via config flow.

## Changes:
* Now it will generate automatically a Niu device so all the sensors and the camera will grouped
![auto device](images/niu_integration_device.png)
* If you select the Last track sensor automatically it will create a camera integration, with the rendered image of your last track.
![last track camera](images/niu_integration_camera.png)

With the thanks to pikka97 !!!

## Setup
1. In Home Assistant's settings under "device and services" click on the "Add integration" button.
2. Search for "Niu Scooters" and click on it.
3. Insert your Niu app companion's credentials and select which sensors do you want.
![config flow](images/config_flow_niu_integration.png)
4. Enjoy your new Niu integration :-)

## Known bugs
See https://github.com/marcelwestrahome/home-assistant-niu-component repository
