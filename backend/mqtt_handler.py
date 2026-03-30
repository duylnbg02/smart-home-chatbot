import paho.mqtt.client as mqtt
import json
import threading
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(r"D:\AI\.env")

class MQTTHandler:
    """
    Xử lý kết nối MQTT với ESP32
    """
    
    def __init__(self, broker_address=None, port=None):
        self.broker_address = broker_address or os.getenv('MQTT_BROKER', 'caa7699a09b24a26b5b945f5db6af243.s1.eu.hivemq.cloud')
        self.port = port or int(os.getenv('MQTT_PORT', '8883'))
        self.client = mqtt.Client(client_id='chatbot-server')
        self.client.tls_set(ca_certs=None, certfile=None, keyfile=None, cert_reqs=mqtt.ssl.CERT_REQUIRED, tls_version=mqtt.ssl.PROTOCOL_TLSv1_2, ciphers=None)
        self.client.tls_insecure_set(False)
        mqtt_username = os.getenv('MQTT_USERNAME', '')
        mqtt_password = os.getenv('MQTT_PASSWORD', '')
        self.client.username_pw_set(mqtt_username, mqtt_password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        self.device_states = {
            'lights': {
                'living_room': False,
                'bedroom': False,
                'bathroom': False
            },
            'ac': {
                'bedroom': False,
                'temperature': 20
            }
        }
        
        self.sensor_data = {
            'temperature': 0.0,
            'humidity': 0.0,
            'light': 0
        }
        
        self.callbacks = []
        self.is_connected = False
        
    def connect(self):
        try:
            self.client.connect(self.broker_address, self.port, keepalive=60)
            self.client.loop_start()
            print(f"🔌 Kết nối MQTT broker tại {self.broker_address}:{self.port}")
        except Exception as e:
            print(f"❌ Lỗi kết nối MQTT: {e}")
            return False
        return True
    
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            print("✅ MQTT broker kết nối thành công")
            self.client.subscribe([
                ('esp32/lights/living_room/status', 1),
                ('esp32/lights/bedroom/status', 1),
                ('esp32/lights/bathroom/status', 1),
                ('esp32/ac/bedroom/status', 1),
                ('esp32/sensors/temperature', 1),
                ('esp32/sensors/humidity', 1),
                ('esp32/sensors/light', 1)
            ])
            print("📡 Đã subscribe các topics")
        else:
            self.is_connected = False
            print(f"❌ Lỗi kết nối MQTT: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            print(f"📨 MQTT Message: {topic} = {payload}")

            if 'lights' in topic and 'status' in topic:
                if 'living_room' in topic:
                    self.device_states['lights']['living_room'] = payload == 'on'
                elif 'bedroom' in topic:
                    self.device_states['lights']['bedroom'] = payload == 'on'
                elif 'bathroom' in topic:
                    self.device_states['lights']['bathroom'] = payload == 'on'
            
            elif 'ac' in topic and 'status' in topic:
                self.device_states['ac']['bedroom'] = payload == 'on'

            elif 'temperature' in topic:
                self.sensor_data['temperature'] = float(payload)
            elif 'humidity' in topic:
                self.sensor_data['humidity'] = float(payload)
            elif 'light' in topic:
                self.sensor_data['light'] = int(payload)
            
            # Gọi callbacks để thông báo cho các listeners
            for callback in self.callbacks:
                callback('message', topic, payload)
                
        except Exception as e:
            print(f"❌ Lỗi xử lý MQTT message: {e}")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback khi ngắt kết nối"""
        if rc != 0:
            self.is_connected = False
            print(f"❌ Mất kết nối MQTT: {rc}")
    
    def send_command(self, device_type, location, value):
        if not self.is_connected:
            print("⚠️  MQTT chưa kết nối, không thể gửi lệnh")
            return False
        
        try:
            if device_type == 'light':
                topic = f'esp32/lights/{location}/command'
                payload = 'on' if value else 'off'
            elif device_type == 'ac':
                topic = f'esp32/ac/{location}/command'
                payload = 'on' if value else 'off'
            elif device_type == 'ac_temp':
                topic = f'esp32/ac/{location}/temperature'
                payload = str(value)
            else:
                return False
            
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ Lệnh gửi thành công: {topic} = {payload}")
                
                # Cập nhật local state
                if device_type == 'light':
                    self.device_states['lights'][location] = value
                elif device_type == 'ac':
                    self.device_states['ac'][location] = value
                elif device_type == 'ac_temp':
                    self.device_states['ac']['temperature'] = value
                
                return True
            else:
                print(f"❌ Lỗi gửi lệnh: {result.rc}")
                return False
                
        except Exception as e:
            print(f"❌ Lỗi send_command: {e}")
            return False
    
    def get_device_states(self):
        return self.device_states
    
    def get_sensor_data(self):
        return self.sensor_data
    
    def register_callback(self, callback):
        self.callbacks.append(callback)

mqtt_handler = None

def get_mqtt_handler():
    global mqtt_handler
    if mqtt_handler is None:
        mqtt_handler = MQTTHandler()
    return mqtt_handler

def init_mqtt():
    global mqtt_handler
    mqtt_handler = get_mqtt_handler()
    return mqtt_handler.connect()
