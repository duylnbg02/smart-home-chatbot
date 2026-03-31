/*
 * ESP32 Smart Home Controller
 * Điều khiển đèn, điều hòa, và cảm biến qua MQTT
 *
 * Board: ESP32 Dev Module
 * Libraries: PubSubClient, DHT11 (or DHT22)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// ============ WiFi Configuration ============
const char *ssid = "YOUR_WIFI_SSID";         // Thay bằng SSID WiFi của bạn
const char *password = "YOUR_WIFI_PASSWORD"; // Thay bằng password WiFi

// ============ MQTT Configuration ============
const char *mqtt_server = "caa7699a09b24a26b5b945f5db6af243.s1.eu.hivemq.cloud";
const int mqtt_port = 8883; // TLS port
const char *mqtt_user = "mqtt-backend";
const char *mqtt_password = "Test1234";

// ============ Pinouts ============
#define LIGHT_LIVING_ROOM_PIN 5 // GPIO5 - Đèn phòng khách
#define LIGHT_BEDROOM_PIN 12    // GPIO12 - Đèn phòng ngủ
#define LIGHT_BATHROOM_PIN 13   // GPIO13 - Đèn phòng tắm
#define AC_BEDROOM_PIN 14       // GPIO14 - Điều hòa phòng ngủ
#define DHT_PIN 4               // GPIO4 - DHT sensor
#define LIGHT_SENSOR_PIN 35     // GPIO35 (ADC) - Cảm biến ánh sáng
#define DHT_TYPE DHT11          // Thay bằng DHT22 nếu dùng sensor khác

// ============ Objects ============
WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHT_PIN, DHT_TYPE);

// ============ Variables ============
unsigned long lastSensorPublish = 0;
const unsigned long SENSOR_PUBLISH_INTERVAL = 5000; // 5 giây

// ============ Setup ============
void setup()
{
  Serial.begin(115200);
  delay(100);

  Serial.println("\n\n=== ESP32 Smart Home Controller ===");

  // Setup pins
  pinMode(LIGHT_LIVING_ROOM_PIN, OUTPUT);
  pinMode(LIGHT_BEDROOM_PIN, OUTPUT);
  pinMode(LIGHT_BATHROOM_PIN, OUTPUT);
  pinMode(AC_BEDROOM_PIN, OUTPUT);

  // Set all outputs to LOW (OFF)
  digitalWrite(LIGHT_LIVING_ROOM_PIN, LOW);
  digitalWrite(LIGHT_BEDROOM_PIN, LOW);
  digitalWrite(LIGHT_BATHROOM_PIN, LOW);
  digitalWrite(AC_BEDROOM_PIN, LOW);

  // Initialize DHT sensor
  dht.begin();

  // Connect to WiFi
  setup_wifi();

  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqtt_callback);

  Serial.println("Setup completed!");
}

// ============ Main Loop ============
void loop()
{
  if (!client.connected())
  {
    mqtt_reconnect();
  }
  client.loop();

  // Publish sensor data periodically
  unsigned long now = millis();
  if (now - lastSensorPublish > SENSOR_PUBLISH_INTERVAL)
  {
    publish_sensor_data();
    lastSensorPublish = now;
  }
}

// ============ WiFi Setup ============
void setup_wifi()
{
  delay(10);
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20)
  {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  }
  else
  {
    Serial.println("Failed to connect to WiFi");
  }
}

// ============ MQTT Reconnect ============
void mqtt_reconnect()
{
  int attempts = 0;
  while (!client.connected() && attempts < 3)
  {
    Serial.print("Attempting MQTT connection...");

    if (client.connect("ESP32_SmartHome", mqtt_user, mqtt_password))
    {
      Serial.println("✓ MQTT connected");

      // Subscribe to command topics
      client.subscribe("esp32/lights/living_room/command");
      client.subscribe("esp32/lights/bedroom/command");
      client.subscribe("esp32/lights/bathroom/command");
      client.subscribe("esp32/ac/bedroom/command");
      client.subscribe("esp32/ac/bedroom/temperature");

      Serial.println("✓ Subscribed to topics");

      // Publish initial status
      client.publish("esp32/lights/living_room/status", "off");
      client.publish("esp32/lights/bedroom/status", "off");
      client.publish("esp32/lights/bathroom/status", "off");
      client.publish("esp32/ac/bedroom/status", "off");
    }
    else
    {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" trying again in 5 seconds");
      delay(5000);
    }
    attempts++;
  }
}

// ============ MQTT Callback ============
void mqtt_callback(char *topic, byte *payload, unsigned int length)
{
  String message = "";
  for (unsigned int i = 0; i < length; i++)
  {
    message += (char)payload[i];
  }

  Serial.print("MQTT Message: ");
  Serial.print(topic);
  Serial.print(" = ");
  Serial.println(message);

  // ===== Light Control =====
  if (strcmp(topic, "esp32/lights/living_room/command") == 0)
  {
    handle_light_command(LIGHT_LIVING_ROOM_PIN, "living_room", message);
  }
  else if (strcmp(topic, "esp32/lights/bedroom/command") == 0)
  {
    handle_light_command(LIGHT_BEDROOM_PIN, "bedroom", message);
  }
  else if (strcmp(topic, "esp32/lights/bathroom/command") == 0)
  {
    handle_light_command(LIGHT_BATHROOM_PIN, "bathroom", message);
  }

  // ===== AC Control =====
  else if (strcmp(topic, "esp32/ac/bedroom/command") == 0)
  {
    if (message == "on")
    {
      digitalWrite(AC_BEDROOM_PIN, HIGH);
      client.publish("esp32/ac/bedroom/status", "on");
      Serial.println("AC turned ON");
    }
    else if (message == "off")
    {
      digitalWrite(AC_BEDROOM_PIN, LOW);
      client.publish("esp32/ac/bedroom/status", "off");
      Serial.println("AC turned OFF");
    }
  }

  // ===== AC Temperature =====
  else if (strcmp(topic, "esp32/ac/bedroom/temperature") == 0)
  {
    int temp = message.toInt();
    Serial.print("Setting AC temperature to: ");
    Serial.println(temp);
    // TODO: Implement PWM or temperature control logic
  }
}

// ============ Light Control Handler ============
void handle_light_command(int pin, String location, String command)
{
  if (command == "on")
  {
    digitalWrite(pin, HIGH);
    String topic = "esp32/lights/" + location + "/status";
    client.publish(topic.c_str(), "on");
    Serial.println("Light " + location + " turned ON");
  }
  else if (command == "off")
  {
    digitalWrite(pin, LOW);
    String topic = "esp32/lights/" + location + "/status";
    client.publish(topic.c_str(), "off");
    Serial.println("Light " + location + " turned OFF");
  }
}

// ============ Publish Sensor Data ============
void publish_sensor_data()
{
  // Read DHT sensor (Temperature & Humidity)
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  // Read light sensor (0-4095 → normalize to lux)
  int rawLight = analogRead(LIGHT_SENSOR_PIN);
  int lux = map(rawLight, 0, 4095, 0, 1000); // Simplified mapping

  // Check if DHT reading is valid
  if (isnan(temperature) || isnan(humidity))
  {
    Serial.println("Failed to read DHT sensor");
    temperature = 0;
    humidity = 0;
  }

  // Publish to MQTT
  if (client.connected())
  {
    // Temperature
    String tempStr = String(temperature, 1);
    client.publish("esp32/sensors/temperature", tempStr.c_str());

    // Humidity
    String humStr = String(humidity, 1);
    client.publish("esp32/sensors/humidity", humStr.c_str());

    // Light
    String lightStr = String(lux);
    client.publish("esp32/sensors/light", lightStr.c_str());

    Serial.print("Sensors published - Temp: ");
    Serial.print(temperature);
    Serial.print("°C, Humidity: ");
    Serial.print(humidity);
    Serial.print("%, Light: ");
    Serial.print(lux);
    Serial.println(" lux");
  }
  else
  {
    Serial.println("MQTT not connected, cannot publish sensors");
  }
}

/*
 * ============ WIRING DIAGRAM ============
 *
 * ESP32 PIN MAPPING:
 *
 * GPIO5   → Light Living Room (Relay/LED)
 * GPIO12  → Light Bedroom (Relay/LED)
 * GPIO13  → Light Bathroom (Relay/LED)
 * GPIO14  → AC Bedroom (Relay)
 * GPIO4   → DHT11/22 (Temperature & Humidity)
 * GPIO35  → Light Sensor (LDR via ADC)
 *
 * RELAY WIRING:
 * Relay IN1 → GPIO5
 * Relay IN2 → GPIO12
 * Relay IN3 → GPIO13
 * Relay IN4 → GPIO14
 * Relay GND → ESP32 GND
 * Relay VCC → ESP32 5V or 3.3V (check relay spec)
 *
 * DHT WIRING:
 * DHT VCC   → ESP32 3.3V
 * DHT GND   → ESP32 GND
 * DHT DATA  → GPIO4
 *
 * LIGHT SENSOR WIRING:
 * LDR + Resistor to GPIO35 (ADC)
 *
 * ============ HOW TO USE ============
 *
 * 1. Install libraries:
 *    - Sketch → Include Library → Manage Libraries
 *    - Search: "PubSubClient" (by Nick O'Leary)
 *    - Search: "DHT sensor library" (by Adafruit)
 *
 * 2. Edit WiFi and MQTT settings
 *
 * 3. Upload to ESP32
 *
 * 4. Open Serial Monitor (9600 baud)
 *
 * 5. Check MQTT broker status
 *
 * ============ MQTT TOPICS ============
 *
 * Commands (publish from server):
 * - esp32/lights/living_room/command    → "on" or "off"
 * - esp32/lights/bedroom/command        → "on" or "off"
 * - esp32/lights/bathroom/command       → "on" or "off"
 * - esp32/ac/bedroom/command            → "on" or "off"
 * - esp32/ac/bedroom/temperature        → integer (16-30)
 *
 * Status (subscribe to server):
 * - esp32/lights/living_room/status     → "on" or "off"
 * - esp32/lights/bedroom/status         → "on" or "off"
 * - esp32/lights/bathroom/status        → "on" or "off"
 * - esp32/ac/bedroom/status             → "on" or "off"
 *
 * Sensors (publish periodically):
 * - esp32/sensors/temperature           → float (e.g., 25.3)
 * - esp32/sensors/humidity              → float (e.g., 60.5)
 * - esp32/sensors/light                 → int (e.g., 300)
 */
