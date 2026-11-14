from flask import Flask, request, jsonify

app = Flask(__name__)

# Umbrales máximos permitidos (Parámetros definidos por el Master)
UMBRALES = {
    "luz_ldr": 800,
    "frecuencia_cardiaca": 120,
    "temperatura": 38.0
}

@app.route('/telemetria', methods=['POST'])
def recibir_telemetria():
    # 1. Leer el JSON enviado por la ESP32
    datos = request.get_json(silent=True)
    if not datos:
        return jsonify({"error": "Formato JSON invalido"}), 400

    id_ente = datos.get("id_ente", "DESCONOCIDO")
    sensores = datos.get("sensores", {})

    print(f"📥 [HTTP POST] Datos de {id_ente}: {sensores}")

    # 2. Evaluar si alguna variable supera los parámetros
    alertas = []
    for variable, valor in sensores.items():
        if variable in UMBRALES and valor > UMBRALES[variable]:
            alertas.append(f"{variable} excedida ({valor} > {UMBRALES[variable]})")

    # 3. Construir y devolver el JSON de respuesta inmediata a la ESP32
    if alertas:
        respuesta = {
            "estado": "ADVERTENCIA",
            "severidad": "CRITICA",
            "mensaje": " | ".join(alertas),
            "alerta_activa": True
        }
        print(f"🚨 [RESPUESTA ENVIADA a {id_ente}] -> {respuesta}\n")
    else:
        respuesta = {
            "estado": "NOMINAL",
            "severidad": "NORMAL",
            "mensaje": "Parametros dentro de rango",
            "alerta_activa": False
        }
        print(f"✅ [RESPUESTA ENVIADA a {id_ente}] -> NOMINAL\n")

    return jsonify(respuesta), 200

if __name__ == '__main__':
    print("🚀 Servidor Master HTTP iniciado en http://172.18.2.48:5000/telemetria")
    app.run(host='0.0.0.0', port=5000)