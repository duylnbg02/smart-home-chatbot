import paho.mqtt.client as mqtt
import os, json
from dotenv import load_dotenv

load_dotenv(r"D:\AI\.env")

class MQTTHandler:
    def __init__(self):
        self.broker = os.getenv('MQTT_BROKER', 'caa7699a09b24a26b5b945f5db6af243.s1.eu.hivemq.cloud')
        self.port = int(os.getenv('MQTT_PORT', '8883'))
        self.client = mqtt.Client(client_id='chatbot-server')
        self.client.tls_set(cert_reqs=mqtt.ssl.CERT_REQUIRED, tls_version=mqtt.ssl.PROTOCOL_TLSv1_2)
        self.client.username_pw_set(os.getenv('MQTT_USERNAME'), os.getenv('MQTT_PASSWORD'))  
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message  
        self.is_connected = False
        self.states = {
            'lights': {'living_room': False, 'bedroom': False, 'bathroom': False},
            'ac': {'bedroom': False, 'temp': 20},
            'sensors': {'temp': 0.0, 'humi': 0.0, 'light': 0}
        }

    def connect(self):
        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
            return True
        except: return False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            client.subscribe([('esp32/lights/+/status', 1), ('esp32/ac/+/status', 1), ('esp32/sensors/+', 1)])

    def on_message(self, client, userdata, msg):
        topic, payload = msg.topic, msg.payload.decode()
        if 'lights' in topic:
            loc = topic.split('/')[2]
            self.states['lights'][loc] = (payload == 'on')
        elif 'sensors' in topic:
            key = topic.split('/')[-1][:4] # temp, humi, ligh
            self.states['sensors'][key] = float(payload)
        elif 'ac' in topic:
            self.states['ac']['bedroom'] = (payload == 'on')

    def send_command(self, dev_type, loc, val):
        if not self.is_connected: return False
        
        topic = f"esp32/{dev_type}/{loc}/command"
        if dev_type == 'ac_temp': topic = f"esp32/ac/{loc}/temperature"
        
        payload = str(val).lower() if isinstance(val, bool) else str(val)
        res = self.client.publish(topic, payload, qos=1)
        return res.rc == mqtt.MQTT_ERR_SUCCESS

# Singleton pattern
mqtt_instance = None

def get_mqtt_handler():
    global mqtt_instance
    if not mqtt_instance: mqtt_instance = MQTTHandler()
    return mqtt_instance

def init_mqtt():
    return get_mqtt_handler().connect()