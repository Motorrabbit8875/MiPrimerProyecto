#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- CONFIGURACIÓN DE RED ---
const char* ssid     = "EXPANYX";
const char* password = "EXPANYX1";
const char* serverUrl = "http://192.168.137.1:5000/telemetria";

// --- PINES DE LEDs ---
const int PIN_LED_VERDE = 2;    // Normal
const int PIN_LED_AMARILLO = 4; // Cambio drástico
const int PIN_LED_ROJO = 5;     // Límite crítico superado

// --- VARIABLES DE ESTADO ---
String astronauta = "Astro 1";
float bpmSimulado = 78.5;
float spo2Simulado = 98.2;
float tempSimulada = 36.5;
int actividadSimulada = 1;

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
  Serial.println("   bpm=130   (Simula pulso alto)");
  Serial.println("   temp=38.5 (Simula fiebre)");
  Serial.println("   ok        (Verifica y desenclava la alarma)");
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
        mandarComandoOk = true; // Se mandará en la siguiente trama POST
      } else {
        Serial.println("\n[INFO] El sistema ya está en verde. No hay alarmas activas que desenclavar.");
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
  }

  // --- 2. FLUJO CONTINUO DE TELEMETRÍA (Nunca se bloquea) ---
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<250> docSalida;
    docSalida["astro"] = astronauta;
    docSalida["bpm"] = bpmSimulado;
    docSalida["spo2"] = spo2Simulado;
    docSalida["temperature"] = tempSimulada;
    docSalida["actividad"] = actividadSimulada;

    // Si el operador tecleó "ok", adjuntamos el comando en la trama
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

      StaticJsonDocument<250> docEntrada;
      DeserializationError error = deserializeJson(docEntrada, payload);

      if (!error) {
        const char* alertaServidor = docEntrada["alerta"];

        // Si mandamos el "ok" y el servidor confirmó que ya regresó a "desactivada", desenclavamos localmente
        if (mandarComandoOk && strcmp(alertaServidor, "desactivada") == 0) {
          alarmaEnclavada = false;
          tipoAlertaActual = "desactivada";
          mandarComandoOk = false;
          Serial.println("[✅ DESENCLAVADO] Operador verificó el incidente. Sistema normalizado.");
        }

        // Si el servidor indica una alerta (ya sea nueva o porque sigue enclavada del lado del servidor), la fijamos
        if (strcmp(alertaServidor, "limite_superado") == 0 || strcmp(alertaServidor, "cambio_drastico") == 0) {
          alarmaEnclavada = true;
          tipoAlertaActual = alertaServidor;
        }

        // --- 3. GESTIÓN DE LEDs SEGÚN EL ENCLAVAMIENTO ---
        if (!alarmaEnclavada) {
          // Verde operativo normal
          digitalWrite(PIN_LED_VERDE, HIGH);
          digitalWrite(PIN_LED_AMARILLO, LOW);
          digitalWrite(PIN_LED_ROJO, LOW);
        } else {
          // Alerta enclavada (se repite hasta recibir el ok)
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

  delay(3000); // Manda telemetría cada 3 segundos de forma constante
}