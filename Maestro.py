from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/telemetria', methods=['POST'])
def recibir_y_validar():
    
    # 1. Deserializa el JSON
    datos = request.get_json()
    
    if not isinstance(datos, dict):
        return jsonify({"error": "El formato debe ser un objeto JSON válido"}), 400

    # 2. Define las llaves obligatorias y sus tipos de datos esperados en Python
    campos_esperados = {
        "bpm": (int, float),  # Acepta enteros o decimales
        "spo2": (int, float),
        "temperature": (int,float)       # Debe ser estrictamente un número entero (0, 1, 2)
    }

    # 3. Valida la existencia y el tipo de cada campo
    for campo, tipos_validos in campos_esperados.items():
        if campo not in datos:
            return jsonify({"error": f"Falta el campo obligatorio: '{campo}'"}), 400
        
        # Valida que el valor recibido coincida con el tipo de dato esperado
        if not isinstance(datos[campo], tipos_validos):
            return jsonify({"error": f"El campo '{campo}' tiene un tipo de dato inválido"}), 400

    # 4. Si pasa todas las pruebas, ya puedes extraer las variables con total seguridad
    hr = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]

    print(f"[VALIDADO] BPM: {hr} | SpO2: {spo2} | Temperatura: {temperature} ")

    return jsonify({"status": "VALIDADO_Y_ACEPTADO"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)