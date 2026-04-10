#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Wi-Fi Credentials ──────────────────────────────────────
const char* WIFI_SSID     = "Pooja";
const char* WIFI_PASSWORD = "poseguide";
const char* BACKEND_IP    = "10.156.233.89";
const int   BACKEND_PORT  = 8000;

const unsigned long SEND_INTERVAL_MS   = 2000;   // POST every 2 seconds
const unsigned long PROFILE_SWITCH_MS  = 4000;  // switch profile every 10 seconds

#define SERIAL_BAUD 115200
#define LED_PIN 2

// ── Profiles ───────────────────────────────────────────────
struct PostureProfile {
  const char* name;
  float torso_pitch, torso_roll, torso_yaw;
  float neck_pitch,  neck_roll,  neck_yaw;
  float flex_value;
};

const PostureProfile PROFILES[] = {
  { "Perfect posture",      5.0,  1.0, 0.0,   5.0,  1.0, 0.0,  10.0 },
  { "Mild slouch",         20.0,  2.0, 0.0,  18.0,  2.0, 0.0,  40.0 },
  { "Bad slouch",          30.0,  3.0, 0.0,  25.0,  2.0, 0.0,  60.0 },
  { "Forward head",        10.0,  1.0, 0.0,  35.0,  1.0, 0.0,  25.0 },
  { "Side lean",            8.0, 18.0, 5.0,  10.0, 12.0, 3.0,  30.0 },
  { "Worst case",          40.0, 20.0,10.0,  45.0, 15.0, 8.0,  90.0 },
};

const int NUM_PROFILES = sizeof(PROFILES) / sizeof(PROFILES[0]);

int currentProfile = 0;
unsigned long lastSendTime    = 0;
unsigned long lastSwitchTime  = 0;
int requestCount = 0;

void sendSensorData();
void scanNetworks();
void printProfileBanner(int idx);

// ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1500);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("\n═══════════════════════════════════════");
  Serial.println("  PoseGuide – Auto Profile Cycling");
  Serial.println("═══════════════════════════════════════");
  Serial.printf("  %d profiles, switching every %lus\n",
                NUM_PROFILES, PROFILE_SWITCH_MS / 1000);
  Serial.printf("  POST every %lus\n", SEND_INTERVAL_MS / 1000);
  Serial.println("═══════════════════════════════════════\n");

  // Step 1: Scan
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true);
  delay(1000);
  scanNetworks();

  // Step 2: Connect
  Serial.printf("\n[WiFi] Connecting to \"%s\"...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    attempts++;
    Serial.print(".");
    if (attempts % 20 == 0) Serial.println();
    digitalWrite(LED_PIN, attempts % 2);
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("\n[WiFi] ✅ Connected!");
    Serial.print("  IP   : "); Serial.println(WiFi.localIP());
    Serial.print("  RSSI : "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
    Serial.println();
    printProfileBanner(currentProfile);
  } else {
    Serial.printf("\n[WiFi] ❌ Failed. Status = %d\n", WiFi.status());
    Serial.println("  → Disable WPA3 in Developer Options on phone");
    while (true) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      delay(300);
    }
  }
}

// ─────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Lost connection — restarting...");
    delay(2000);
    ESP.restart();
  }

  unsigned long now = millis();

  // Switch profile every PROFILE_SWITCH_MS
  if (now - lastSwitchTime >= PROFILE_SWITCH_MS) {
    lastSwitchTime = now;
    currentProfile = (currentProfile + 1) % NUM_PROFILES;
    printProfileBanner(currentProfile);
  }

  // Send POST every SEND_INTERVAL_MS
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    sendSensorData();
  }
}

// ─────────────────────────────────────────────────────────
void printProfileBanner(int idx) {
  const PostureProfile& p = PROFILES[idx];
  Serial.println("\n────────────────────────────────────────");
  Serial.printf("  PROFILE %d/%d: %s\n", idx + 1, NUM_PROFILES, p.name);
  Serial.printf("  torso: pitch=%.1f  roll=%.1f  yaw=%.1f\n",
                p.torso_pitch, p.torso_roll, p.torso_yaw);
  Serial.printf("  neck : pitch=%.1f  roll=%.1f  yaw=%.1f\n",
                p.neck_pitch, p.neck_roll, p.neck_yaw);
  Serial.printf("  flex : %.1f\n", p.flex_value);
  Serial.println("────────────────────────────────────────\n");
}

// ─────────────────────────────────────────────────────────
void sendSensorData() {
  const PostureProfile& p = PROFILES[currentProfile];
  requestCount++;
  Serial.printf("[POST] #%d  profile=%s  ", requestCount, p.name);

  StaticJsonDocument<256> doc;
  JsonObject torso = doc.createNestedObject("torso");
  torso["pitch"] = p.torso_pitch;
  torso["roll"]  = p.torso_roll;
  torso["yaw"]   = p.torso_yaw;
  JsonObject neck = doc.createNestedObject("neck");
  neck["pitch"] = p.neck_pitch;
  neck["roll"]  = p.neck_roll;
  neck["yaw"]   = p.neck_yaw;
  doc["flex_value"] = p.flex_value;
  doc["timestamp"]  = (long)millis();

  String payload;
  serializeJson(doc, payload);

  String url = String("http://") + BACKEND_IP + ":" + BACKEND_PORT + "/api/sensor-data";
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  unsigned long t0 = millis();
  int code = http.POST(payload);
  unsigned long elapsed = millis() - t0;

  Serial.printf("HTTP %d  (%lums)\n", code, elapsed);

  if (code == 200) {
    String response = http.getString();
    DynamicJsonDocument resp(1024);
    if (!deserializeJson(resp, response)) {
      const char* condition = resp["classification"]["condition"];
      int score = resp["classification"]["score"];
      Serial.printf("  ✅  condition=%-20s  score=%d\n", condition, score);
    } else {
      Serial.println("  ✅  " + response.substring(0, 100));
    }
  } else if (code == -1) {
    Serial.println("  ❌  Connection refused — is backend running?");
  } else if (code == -11) {
    Serial.println("  ❌  Timeout — check IP/firewall");
  } else {
    Serial.println("  ⚠️   " + http.getString());
  }

  http.end();
}

// ─────────────────────────────────────────────────────────
void scanNetworks() {
  Serial.println("[SCAN] Scanning for networks...");
  int n = WiFi.scanNetworks();
  if (n == 0) { Serial.println("[SCAN] No networks found!"); return; }

  Serial.printf("[SCAN] Found %d network(s):\n\n", n);
  Serial.println("   # | RSSI | CH | ENC        | SSID");
  Serial.println("  ---|------|----|------------|------------------------------");

  bool found = false;
  for (int i = 0; i < n; i++) {
    String enc;
    switch (WiFi.encryptionType(i)) {
      case WIFI_AUTH_OPEN:          enc = "Open";      break;
      case WIFI_AUTH_WEP:           enc = "WEP";       break;
      case WIFI_AUTH_WPA_PSK:       enc = "WPA";       break;
      case WIFI_AUTH_WPA2_PSK:      enc = "WPA2";      break;
      case WIFI_AUTH_WPA_WPA2_PSK:  enc = "WPA/WPA2";  break;
      case WIFI_AUTH_WPA3_PSK:      enc = "WPA3";      break;
      case WIFI_AUTH_WPA2_WPA3_PSK: enc = "WPA2/WPA3"; break;
      default:                      enc = "Unknown";   break;
    }
    bool isTarget = (WiFi.SSID(i) == String(WIFI_SSID));
    if (isTarget) found = true;
    Serial.printf("  %2d | %4d | %2d | %-10s | %s%s\n",
      i+1, WiFi.RSSI(i), WiFi.channel(i),
      enc.c_str(), WiFi.SSID(i).c_str(),
      isTarget ? "  ← TARGET" : "");
  }

  if (!found)
    Serial.printf("\n  ⚠️  \"%s\" not found — check hotspot name and 2.4GHz band\n", WIFI_SSID);

  WiFi.scanDelete();
  delay(500);
}