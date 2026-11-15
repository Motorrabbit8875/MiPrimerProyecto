#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- CONFIGURACIÓN DE RED ---
const char* ssid     = "TU_HOTSPOT_WIFI_2.4GHz";
const char* password = "TU_PASSWORD_WIFI";
const char* serverUrl = "http://192.168.137.1:5000/telemetria";

// --- PINES DE LEDs ---
const int PIN_LED_VERDE = 2;    // Normal
const int PIN_LED_AMARILLO = 4; // Cambio drástico
const int PIN_LED_ROJO = 5;     // Límite crítico superado

// --- VARIABLES DE TELEMETRÍA E INTERACTIVAS ---
String astronauta = "Astro 1";
float bpmSimulado = 78.5;
float spo2Simulado = 98.2;
float tempSimulada = 36.5;
float respRateSimulado = 16.0;
float bpSysSimulado = 120.0;
float bpDiaSimulado = 80.0;
float radiationSimulado = 0.05;
int actividadSimulada = 0; // 0 = Reposo, 1 = Activo

bool alarmaEnclavada = false;
String tipoAlertaActual = "desactivada";
bool mandarComandoOk = false;

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_AMARILLO, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);

  WiFi.begin(ssid, password);
  Serial.print("Conectando al Hotspot");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[RED] ¡Conectado con éxito!");

  Serial.println("\n========================================");
  Serial.println(" COMANDOS DISPONIBLES EN EL SERIAL:");
  Serial.println("   bpm=130   | temp=38.5 | resp=28");
  Serial.println("   sys=140   | dia=90    | rad=0.6");
  Serial.println("   act=1     (1=Activo / 0=Reposo)");
  Serial.println("   ok        (Verifica y desenclava alarma)");
  Serial.println("========================================\n");
}

void loop() {
  // --- 1. LEER COMANDOS DEL OPERADOR EN LA TERMINAL ---
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();
    
    if (comando.equalsIgnoreCase("ok")) {
      if (alarmaEnclavada) {
        Serial.println("\n[OPERADOR] Enviando comando 'ok' para verificar y desenclavar...");
        mandarComandoOk = true;
      } else {
        Serial.println("\n[INFO] El sistema ya está en verde. No hay alarmas activas.");
      }
    }
    else if (comando.startsWith("bpm=")) {
      bpmSimulado = comando.substring(4).toFloat();
      Serial.printf("--> [CONFIG] BPM fijado a: %.1f\n", bpmSimulado);
    } 
    else if (comando.startsWith("temp=")) {
      tempSimulada = comando.substring(5).toFloat();
      Serial.printf("--> [CONFIG] Temperatura fijada a: %.1f\n", tempSimulada);
    }
    else if (comando.startsWith("resp=")) {
      respRateSimulado = comando.substring(5).toFloat();
      Serial.printf("--> [CONFIG] Frecuencia Respiratoria fijada a: %.1f\n", respRateSimulado);
    }
    else if (comando.startsWith("sys=")) {
      bpSysSimulado = comando.substring(4).toFloat();
      Serial.printf("--> [CONFIG] Presión Sistólica fijada a: %.1f\n", bpSysSimulado);
    }
    else if (comando.startsWith("dia=")) {
      bpDiaSimulado = comando.substring(4).toFloat();
      Serial.printf("--> [CONFIG] Presión Diastólica fijada a: %.1f\n", bpDiaSimulado);
    }
    else if (comando.startsWith("rad=")) {
      radiationSimulado = comando.substring(4).toFloat();
      Serial.printf("--> [CONFIG] Radiación fijada a: %.2f\n", radiationSimulado);
    }
    else if (comando.startsWith("act=")) {
      actividadSimulada = comando.substring(4).toInt();
      Serial.printf("--> [CONFIG] Actividad fijada a: %d (%s)\n", actividadSimulada, actividadSimulada == 1 ? "ACTIVO" : "REPOSO");
    }
  }

  // --- 2. FLUJO CONTINUO DE TELEMETRÍA ---
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    // Capacidad aumentada a 400 para soportar todas las variables
    StaticJsonDocument<400> docSalida;
    docSalida["astro"] = astronauta;
    docSalida["bpm"] = bpmSimulado;
    docSalida["spo2"] = spo2Simulado;
    docSalida["temperature"] = tempSimulada;
    docSalida["resp_rate"] = respRateSimulado;
    docSalida["bp_sys"] = bpSysSimulado;
    docSalida["bp_dia"] = bpDiaSimulado;
    docSalida["radiation"] = radiationSimulado;
    docSalida["actividad"] = actividadSimulada;

    if (mandarComandoOk) {
      docSalida["comando"] = "ok";
    }

    String jsonBody;
    serializeJson(docSalida, jsonBody);

    Serial.println("\n----------------------------------------");
    Serial.println("[ENVIANDO TELEMETRÍA AL MAESTRO]:");
    Serial.println(jsonBody);

    int httpResponseCode = http.POST(jsonBody);

    if (httpResponseCode > 0) {
      String payload = http.getString();
      Serial.println("[RESPUESTA DEL MAESTRO]:");
      Serial.println(payload);

      StaticJsonDocument<300> docEntrada;
      DeserializationError error = deserializeJson(docEntrada, payload);

      if (!error) {
        const char* alertaServidor = docEntrada["alerta"];

        if (mandarComandoOk && strcmp(alertaServidor, "desactivada") == 0) {
          alarmaEnclavada = false;
          tipoAlertaActual = "desactivada";
          mandarComandoOk = false;
          Serial.println("[✅ DESENCLAVADO] Operador verificó el incidente. Sistema normalizado.");
        }

        if (strcmp(alertaServidor, "limite_superado") == 0 || strcmp(alertaServidor, "cambio_drastico") == 0) {
          alarmaEnclavada = true;
          tipoAlertaActual = alertaServidor;
        }

        // --- 3. GESTIÓN DE LEDs SEGÚN EL ENCLAVAMIENTO ---
        if (!alarmaEnclavada) {
          digitalWrite(PIN_LED_VERDE, HIGH);
          digitalWrite(PIN_LED_AMARILLO, LOW);
          digitalWrite(PIN_LED_ROJO, LOW);
        } else {
          digitalWrite(PIN_LED_VERDE, LOW);
          
          if (tipoAlertaActual == "cambio_drastico") {
            digitalWrite(PIN_LED_AMARILLO, HIGH);
            digitalWrite(PIN_LED_ROJO, LOW);
          } else if (tipoAlertaActual == "limite_superado") {
            digitalWrite(PIN_LED_AMARILLO, LOW);
            digitalWrite(PIN_LED_ROJO, HIGH);
          }
        }
      }
    } else {
      Serial.printf("[ERROR] HTTP falló: %s\n", http.errorToString(httpResponseCode).c_str());
    }

    http.end();
  } else {
    Serial.println("[RED] WiFi desconectado. Reconectando...");
    WiFi.reconnect();
  }

  delay(3000);
}