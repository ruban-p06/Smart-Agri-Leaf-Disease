#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>

/* ========== PIN DEFINITIONS ========== */
#define RELAY_PUMP     26
#define RELAY_VALVE   27
#define SOIL_PIN      34
#define WATER_PIN     35

#define DHTPIN        4       // DHT data pin
#define DHTTYPE       DHT11   // or DHT22

/* ========== CALIBRATION VALUES ========== */
#define SOIL_DRY      3000
#define WATER_HIGH    2000

/* ========== WIFI ========== */
const char* ssid = "agri1234";
const char* password = "agri1234";

/* ========== OBJECTS ========== */
WebServer server(80);
DHT dht(DHTPIN, DHTTYPE);

/* ========== STATUS STRINGS ========== */
String pumpStatus = "OFF";
String valveStatus = "OFF";

/* ========== SETUP ========== */
void setup() {
  Serial.begin(115200);

  pinMode(RELAY_PUMP, OUTPUT);
  pinMode(RELAY_VALVE, OUTPUT);

  // LOW-level trigger relays OFF
  digitalWrite(RELAY_PUMP, HIGH);
  digitalWrite(RELAY_VALVE, HIGH);

  dht.begin();

  /* ---------- WIFI ---------- */
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  /* ---------- WEB SERVER ---------- */
  server.on("/data", sendSensorData);
  server.begin();

  Serial.println("ESP32 IRRIGATION SYSTEM STARTED");
}

/* ========== LOOP ========== */
void loop() {

  int soilRaw  = analogRead(SOIL_PIN);
  int waterRaw = analogRead(WATER_PIN);

  bool soilDry   = (soilRaw > SOIL_DRY);
  bool waterHigh = (waterRaw > WATER_HIGH);

  /* ---------- PUMP CONTROL ---------- */
  if (soilDry) {
    digitalWrite(RELAY_PUMP, LOW);
    pumpStatus = "ON";
  } else {
    digitalWrite(RELAY_PUMP, HIGH);
    pumpStatus = "OFF";
  }

  /* ---------- SOLENOID CONTROL ---------- */
  if (waterHigh) {
    digitalWrite(RELAY_VALVE, LOW);
    valveStatus = "ON";
  } else {
    digitalWrite(RELAY_VALVE, HIGH);
    valveStatus = "OFF";
  }

  /* ---------- DEBUG ---------- */
  Serial.println("----------------------------");
  Serial.print("Soil RAW   : "); Serial.println(soilRaw);
  Serial.print("Water RAW  : "); Serial.println(waterRaw);
  Serial.print("Pump       : "); Serial.println(pumpStatus);
  Serial.print("Valve      : "); Serial.println(valveStatus);

  server.handleClient();
  delay(2000);
}

/* ========== SEND JSON DATA ========== */
void sendSensorData() {

  int soilMoisture = analogRead(SOIL_PIN);
  int waterLevel   = analogRead(WATER_PIN);
  float temperature = dht.readTemperature(); // Celsius

  if (isnan(temperature)) {
    temperature = -1; // error value
  }

  String json = "{";
  json += "\"soil_moisture\":" + String(soilMoisture) + ",";
  json += "\"water_level\":" + String(waterLevel) + ",";
  json += "\"temperature\":" + String(temperature, 1) + ",";
  json += "\"pump_status\":\"" + pumpStatus + "\",";
  json += "\"solenoid_status\":\"" + valveStatus + "\"";
  json += "}";

  server.send(200, "application/json", json);
}