#!/usr/bin/python

# HC-SR05 distance calculation taking into account the temperature
# - Read temperature from a MQTT topic
# - Write distance to another MQTT topic

import RPi.GPIO as GPIO
import threading
import time
import json
import os
import paho.mqtt.client as mqtt
import math
from datetime import datetime

global GPIO_TRIGGER, GPIO_ECHO, MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_TOPIC, MQTT_TOPIC_TEMP, MQTT_TOPIC_TEMP_ATTR, INPUT_TEMP, MEASURE_INTERVAL, MEASURE_THRESHOLD, VERBOSE, prev_dist

def get_env(key, fallback):
  value = os.getenv(str(key))
  #print(">>> DEBUG: Look for env key: "+str(key)+" with default value: "+str(fallback))
  #print("    Env value: "+str(value))
  if value is not None:
    return value
  return fallback

# Variables
GPIO_TRIGGER         = int(get_env('GPIO_TRIGGER', 23))
GPIO_ECHO            = int(get_env('GPIO_ECHO', 24))
MQTT_HOST            = get_env('MQTT_HOST', 'mosquitto')
MQTT_PORT            = int(get_env('MQTT_PORT', 1883))
MQTT_USERNAME        = get_env('MQTT_USERNAME', 'hcsr04')
MQTT_PASSWORD        = get_env('MQTT_PASSWORD', '******')
MQTT_TOPIC           = get_env('MQTT_TOPIC', 'hcsr042mqtt/distancemeter')
MQTT_TOPIC_TEMP      = get_env('MQTT_TOPIC_TEMP', 'zigbee2mqtt/zigbee_poolroom_temp')
MQTT_TOPIC_TEMP_ATTR = get_env('MQTT_TOPIC_TEMP_ATTR', 'temperature')
INPUT_TEMP           = float(get_env('INPUT_TEMP', 20))
MEASURE_INTERVAL     = float(get_env('MEASURE_INTERVAL', 10))
MEASURE_THRESHOLD    = float(get_env('MEASURE_THRESHOLD', 0.5))
VERBOSE              = int(get_env('VERBOSE', 0))

prev_dist = int(0)
config = f"""
HC-SR05 device measurement

GPIO settings:
- Trigger: {GPIO_TRIGGER}
- Echo   : {GPIO_ECHO}

MQTT:
- Host : {MQTT_HOST}
- Port : {MQTT_PORT}
- Username : {MQTT_USERNAME}
- Write Distance Topic: {MQTT_TOPIC}
- Read Temperature Topic: {MQTT_TOPIC_TEMP}
- Read Temperature Topic Attribute: {MQTT_TOPIC_TEMP_ATTR}

Script Parameters:
- Initial Temperature: {INPUT_TEMP}°C (Will be updated when Temperature sensor will publish MQTT message)
- Measure Interval: {MEASURE_INTERVAL} seconds
- Measure Threashold: {MEASURE_THRESHOLD} cm
- Verbose output: {VERBOSE}
"""
print(config)

GPIO.setmode(GPIO.BCM)             # GPIO Mode (BOARD / BCM)
GPIO.setup(GPIO_TRIGGER, GPIO.OUT) # Set GPIO direction OUT
GPIO.setup(GPIO_ECHO, GPIO.IN)     # Set GPIO direction IN

def on_connect(client, userdata, flags, rc):
  global MQTT_TOPIC_TEMP
  if VERBOSE: print(">>> DEBUG: on_connect callback")
  if VERBOSE: print(">>>        Connected with result code "+str(rc))
  if VERBOSE: print(">>>        Subscribe on %s topic" % MQTT_TOPIC_TEMP)
  client.subscribe(MQTT_TOPIC_TEMP) # Subscribe to the MQTT temperature sensor topic
  
def on_message(client, userdata, msg):
  global INPUT_TEMP, MQTT_TOPIC_TEMP, MQTT_TOPIC_TEMP_ATTR
  m_decode=str(msg.payload.decode("utf-8","ignore"))
  m_in=json.loads(m_decode)
  INPUT_TEMP = m_in[MQTT_TOPIC_TEMP_ATTR]
  if VERBOSE: print(">>> DEBUG: On Message callback")
  print("TMP: Temperature message received from MQTT topic %s (Attr: %s). New temperature: %.2f°C" % (MQTT_TOPIC_TEMP, MQTT_TOPIC_TEMP_ATTR, INPUT_TEMP))


def on_publish(client, userdata, mid):
  global VERBOSE
  if VERBOSE: print(">>> DEBUG: on_publish callback.")
  if VERBOSE: print(">>>        Publish callback. Message ID: %.0f" % mid)
  
def distance():
  GPIO.output(GPIO_TRIGGER, True) # Set Trigger to HIGH
  time.sleep(0.00001) # Set Trigger after 0.01ms to LOW
  GPIO.output(GPIO_TRIGGER, False)
  StartTime = time.time()
  StopTime = time.time()
  while GPIO.input(GPIO_ECHO) == 0:
    StartTime = time.time() # Save StartTime
  while GPIO.input(GPIO_ECHO) == 1:
    StopTime = time.time() # Save time of arrival
  TimeElapsed = StopTime - StartTime # Time difference between start and arrival
  # multiply with the sonic speed (34300 cm/s at 20°C otherwise soundSpeed = 331.3 + (0.606 * tempAir) in m/s)
  # and divide by 2, because there and back
  # distance = (TimeElapsed * 34300) / 2
  distance = ( TimeElapsed * ( 331.3 + 0.606 * INPUT_TEMP ) * 100 ) / 2
  print("RAW: StartTime: %f, StopTime: %f, TimeElapsed: %f, distance = %.2f cm, temp: %.2f°C" % (StartTime, StopTime, TimeElapsed, distance,INPUT_TEMP))    
  return distance, TimeElapsed, StartTime

def subscribing():
  client.loop_forever()

def main():
  global prev_dist
  client.on_publish = on_publish
  time.sleep(2)
  try:
    while True:
      dist_tab = distance()
      dist = dist_tab[0]
      if not math.isclose(prev_dist, dist, abs_tol=MEASURE_THRESHOLD):
        print("PUB: Tolerance threashold of %.2f cm exceeded (prev dist: %.2f, new dist: %.2f). Publish new distance to MQTT topic %s" % (MEASURE_THRESHOLD, prev_dist, dist, MQTT_TOPIC))
        payload = "{\"distance\": %.2f, \"time\": %f, \"duration\": %.6f, \"temp\": %.2f}" % (dist,dist_tab[2],dist_tab[2],INPUT_TEMP)
        print("PUB: payload: %s" % payload)
        client.publish(MQTT_TOPIC, payload)
      prev_dist = dist
      time.sleep(MEASURE_INTERVAL)
  except KeyboardInterrupt:
    print("Stopped by user")
    GPIO.cleanup()
    client.unsubscribe(MQTT_TOPIC_TEMP)
    client.disconnect()

# MQTT
client = mqtt.Client("hc-sr04")
client.on_connect = on_connect
client.username_pw_set(username=MQTT_USERNAME,password=MQTT_PASSWORD)
client.connect(host=MQTT_HOST, port=MQTT_PORT, keepalive=60)
  
# Separated threads (subscribe and publish)
sub=threading.Thread(target=subscribing)
pub=threading.Thread(target=main)

### Start MAIN
sub.start()
pub.start()
