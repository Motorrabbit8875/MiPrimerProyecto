from flask import Flask, request, jsonify

app = Flask(__name__)

def evaluar_variable(nombre, valor):
    if nombre == "bpm":
        # Todo el rango 65-80 se considera Estable; solo cambia si se sale del rango
        if 65 <= valor <= 80:
            return "Estable"
        else:
            return "Peligro"

    elif nombre == "spo2":
        if 97 <= valor <= 100:
            return "Estable"
        elif 95 <= valor < 97:
            return "Alerta"
        else:
            return "Peligro"

    elif nombre == "temperature":
        if 36.5 <= valor <= 36.9:
            return "Estable"
        elif 36.1 <= valor <= 37.2:
            return "Alerta"
        else:
            return "Peligro"

@app.route('/telemetria', methods=['POST'])
def recibir_y_validar():
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({"error": "El formato debe ser un objeto JSON válido"}), 400

    campos_esperados = {
        "bpm": (int, float),
        "spo2": (int, float),
        "temperature": (int, float)
    }

    for campo, tipos_validos in campos_esperados.items():
        if campo not in datos:
            return jsonify({"error": f"Falta el campo obligatorio: '{campo}'"}), 400
        if isinstance(datos[campo], bool) or not isinstance(datos[campo], tipos_validos):
            return jsonify({"error": f"El campo '{campo}' tiene un tipo de dato inválido"}), 400

    astro = datos.get("astro", "Astro 1")
    hr = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]

    estados = [
        evaluar_variable("bpm", hr),
        evaluar_variable("spo2", spo2),
        evaluar_variable("temperature", temperature)
    ]

    if "Peligro" in estados:
        estado_general = "Peligro"
    elif "Alerta" in estados:
        estado_general = "Alerta"
    else:
        estado_general = "Estable"

    print(f"[{astro}: {estado_general}] BPM: {hr} | SPO2: {spo2} | Temperatura: {temperature}")

    respuesta = {
        "astro": astro,
        "estado": estado_general,
        "BPM": hr,
        "SPO2": spo2,
        "Temperatura": temperature
    }

    return jsonify(respuesta), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)