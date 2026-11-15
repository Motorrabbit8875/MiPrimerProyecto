from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# Configuración de límites clínicos e incremento máximo (salto drástico permitido entre lecturas)
CONFIG_LIMITES = {
    "bpm": {"min": 50, "max": 120, "salto_max": 25},
    "spo2": {"min": 90, "max": 100, "salto_max": 5},
    "temperature": {"min": 35.0, "max": 38.5, "salto_max": 1.0},
    "actividad": {"min": 0, "max": 1, "salto_max": 1}
}

# Memoria global en RAM por astronauta (Búfer circular deque de tamaño 6 para historial reciente)
estado_astronautas = {}

def obtener_o_crear_astro(astro_id):
    if astro_id not in estado_astronautas:
        estado_astronautas[astro_id] = {
            "historial": {
                "bpm": deque(maxlen=6),
                "spo2": deque(maxlen=6),
                "temperature": deque(maxlen=6),
                "actividad": deque(maxlen=6)
            }
        }
    return estado_astronautas[astro_id]

@app.route('/telemetria', methods=['POST'])
def recibir_telemetria():
    # 1. Deserializar el JSON recibido
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "Formato JSON inválido"}), 400

    # 2. Validar campos obligatorios según el contrato acordado
    astro = datos.get("astro")
    if not astro:
        return jsonify({"error": "Falta el campo obligatorio: 'astro'"}), 400

    campos_requeridos = ["bpm", "spo2", "temperature", "actividad"]
    for campo in campos_requeridos:
        if campo not in datos:
            return jsonify({"error": f"Falta el campo obligatorio: '{campo}'"}), 400
        if not isinstance(datos[campo], (int, float)) or isinstance(datos[campo], bool):
            return jsonify({"error": f"El campo '{campo}' tiene un tipo de dato inválido"}), 400

    # Extracción de valores
    bpm = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]
    actividad = datos["actividad"]

    # 3. Inicializar / Obtener memoria del astronauta
    espacio_astro = obtener_o_crear_astro(astro)
    historial = espacio_astro["historial"]

    # 4. Evaluación de la lógica de negocio (Límites vs Cambios drásticos)
    tipo_alerta = "desactivada"
    mensaje_salida = "Datos procesados correctamente"

    # Mapeo de variables entrantes para validarlas contra la configuración
    valores_actuales = {
        "bpm": bpm,
        "spo2": spo2,
        "temperature": temperature,
        "actividad": actividad
    }

    for variable, valor in valores_actuales.items():
        cfg = CONFIG_LIMITES[variable]
        hist = historial[variable]

        # A. Revisar límite superado (fuera de rango absoluto)
        if valor < cfg["min"] or valor > cfg["max"]:
            tipo_alerta = "limite_superado"
            mensaje_salida = f"Alerta crítica: {variable} fuera de rango ({valor})"
            break

        # B. Revisar cambio drástico (salto respecto al valor anterior inmediato)
        if len(hist) > 0:
            ultimo_valor = hist[-1]
            cambio = abs(valor - ultimo_valor)
            if cambio > cfg["salto_max"]:
                tipo_alerta = "cambio_drastico"
                mensaje_salida = f"Alerta dinámica: salto brusco en {variable} (Δ={cambio:.1f})"
                break

        # Agregar al historial en RAM
        hist.append(valor)

    # Imprimir en consola de la laptop para supervisión local
    print(f"[{astro}] BPM: {bpm} | SpO2: {spo2} | Temp: {temperature} | Act: {actividad} ---> Alerta: {tipo_alerta}")

    # 5. Respuesta JSON estructurada hacia el esclavo (ESP32)
    respuesta_esclavo = {
        "status": "OK",
        "astro": astro,
        "alerta": tipo_alerta,
        "mensaje": mensaje_salida
    }

    return jsonify(respuesta_esclavo), 200

if __name__ == '__main__':
    # Servidor abierto a la red local (Hotspot 2.4 GHz) en el puerto 5000
    app.run(host='0.0.0.0', port=5000)