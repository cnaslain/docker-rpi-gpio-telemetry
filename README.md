
Docker rpi gpio telemetry
====

Goal: Create an automation in Home Assistant to power on a pump and drain my parent's poolroom when water level is rising up to a certain level.

To do this, I use an ultrasonic distance sensor (HC-SR05) connected to a Raspberry Pi (GPIO) to measure a distance. The principle is simple: Measure the time an acoustic echo takes to return to the sensor. Multiply it by the sound speed in air and divide it by two (back and forth). The problem is that the air sound speed depends on the temperature. The temperature is retrieved from an MQTT broker, sent by an air temperature and humidity zigbee sensor. With this value, we can calculate a more accurate distance that won't vary between winter and summer (30 °C of temperature difference!).

I did not want to install in my Raspberry Pi any specific software to pilot the device (development tools like gcc to build the GPIO python library, etc.) nor create system services to manage the sensor. The HC-SR05 device management program is driven by a docker service like any other domotic assets (Mosquitto, Home Assistant, zigbee2mqtt, etc.).


Hardware
----

Don't forget to add the 1 kΩ and 2 kΩ resistors to protect the Raspberry Pi inputs.
image::https://www.framboise314.fr/wp-content/uploads/2014/11/mesure_ultrasons_03.jpg[Electronic diagram]
https://www.framboise314.fr/mesure-de-distance-par-ultrasons-avec-le-raspberry-pi/[Source]

Software
----

The main program is `measure.py`. Here are the environment variables you can setup:

| Variable name | Default value | Purpose | 
|:-------------:|:-------------:|:-------:|
| GPIO_TRIGGER  | 23 | GPIO trigger pin |
| GPIO_ECHO     | 24 | GPIO echo pin |
| MQTT_HOST     | mosquitto | MQTT broker host name (must be reacheable from this container)|
| MQTT_PORT     | 1883 | MQTT broker port |
| MQTT_USERNAME | hcsr04 | MQTT broker user name |
| MQTT_PASSWORD | ****** | MQTT broker user password |
| MQTT_TOPIC    | hcsr042mqtt/distancemeter | MQTT topic to publish the distance data |
| MQTT_TOPIC_TEMP | zigbee2mqtt/zigbee_poolroom_temp | MQTT topic to subscribe to to get the air temperature value |
| MQTT_TOPIC_TEMP_ATTR | temperature | Name of the air temperature topic value attribute to get the temperature info |
| INPUT_TEMP    | 20 | Initial value of the air temperature (in °C)|
| MEASURE_INTERVAL | 10 | Interval between to distance measures (in seconds) |
| MEASURE_THRESHOLD| 0.5 | Threshold distance; if the difference between two measures is less that this value, no message will be published to MQTT (in cm) |
| VERBOSE | 0 | Verbose output option (boolean 0|1) |

- Build the docker image:

````bash
docker build -t hc-sr04 .
````

- Connect the HC-SR05 device with the four wires and run docker (add more environment variables if needed). Examples of commands:

````bash
docker run -it --rm --privileged -e MQTT_PASSWORD='*****' hc-sr04
docker run -it --rm --privileged --workdir=/workspace -v $(pwd):/workspace --network=ha_network --entrypoint=bash hc-sr04
````

- Example of my docker-compose configuration (the `${MQTT_HCSR04_PASSWORD}` is set into a `.env` file):

````bash
version: '3'

networks:
  ha_network:
    external: true

services:

  hcsr04:
    container_name: hcsr04
    image: hc-sr04
    environment:
      MQTT_PASSWORD: ${MQTT_HCSR04_PASSWORD}
      VERBOSE: 1
    restart: always
    networks:
      - ha_network
    privileged: true

  mosquitto:
    container_name: mosquitto
    image: eclipse-mosquitto:2.0.18
    restart: always
    deploy:
      resources:
        limits:
          memory: 125M
    networks:
      - ha_network
    ports:
       - '1883:1883'
    volumes:
      - mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto/etc/mosquitto/passwd:/etc/mosquitto/passwd
      - mosquitto/data:/mosquitto/data
      - mosquitto/log:/mosquitto/log
    healthcheck:
      test: ["CMD", "mosquitto_sub", "-h", "127.0.0.1", "-p", "1880", "-t", "'topic'", "-C", "1", "-E", "-i", "probe", "-W", "3" ]
      interval: 10s
      timeout: 10s
      retries: 6
````

Credits
----

Some code that helps to create the python program:
- https://www.gotronic.fr/pj2-guide-us-hc-sr04-raspberry-pi-2310.pdf (HC-SR05)
- https://www.framboise314.fr/docs/The-MagPi-issue-27-en.pdf (Mag Pi Page 18)
- https://www.framboise314.fr/mesure-de-distance-par-ultrasons-avec-le-raspberry-pi/
- https://raspberry-lab.fr/Composants/Mesure-de-distance-avec-HC-SR04-Raspberry-Francais/
- https://community.home-assistant.io/t/ultrasonic-sensor-gpio-display-value-on-home-assistant/47695/9
- https://stackoverflow.com/a/59039940 (Threading)
