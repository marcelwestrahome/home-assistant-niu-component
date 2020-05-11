# niu

Home assistant niu sensor component to read the parameters of your scooter
for more scooters just add the components again with increasing the scooter id
scooter id 0 (one scooter)
scooter id 1 (two scooters)
etc

Username and password are the credentials of the niu app.

At this moment the NIU sport plus has a bug, at least this type scooter stops after a certain time updating.
When this happen, component will show the last updated values.
With a restart of your your HA, you need to turn on your scooter for a short time to see all sensor values.
Niu promises with a new firmware to solve this problem.
Location is added as attributes to scooter_connected sensor

Installation:
copy "_ init_.py, manifest.json, sensor.py" to custom_components\niu directory
see configuration.yaml for adding the sensors to your system, change email address, password and country
restart home assistant

Need some time to make it  more official HA component, but his one stil works 


