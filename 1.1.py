from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# 1. Configuración de límites clínicos (I) y umbrales de Rango Móvil máximo (MR)
CONFIG_IMR = {
    "bpm": {"min": 70, "max": 90, "mr_max": 15},
    "spo2": {"min": 95, "max": 100, "mr_max": 3},
    "temperature": {"min": 36.1, "max": 37.2, "mr_max": 0.5}
}

# Memoria histórica independiente por astronauta (guarda las últimas 6 lecturas de cada variable)
historial_entes = {}

def detectar_tendencia(valores):
    """Detecta si 6 lecturas consecutivas suben o bajan de forma estricta."""
    if len(valores) < 6:
        return False
    lista = list(valores)
    subiendo = all(lista[i] < lista[i + 1] for i in range(5))
    bajando = all(lista[i] > lista[i + 1] for i in range(5))
    return subiendo or bajando

def evaluar_imr(astro, variable, valor_actual):
    cfg = CONFIG_IMR[variable]
    
    # Inicializar memoria si es la primera vez que reporta este astronauta
    if astro not in historial_entes:
        historial_entes[astro] = {
            "bpm": deque(maxlen=6),
            "spo2": deque(maxlen=6),
            "temperature": deque(maxlen=6)
        }
    
    ventana = historial_entes[astro][variable]
    
    # Calcular Rango Móvil (MR = |Xt - Xt-1|) si existe al menos una lectura previa
    mr = abs(valor_actual - ventana[-1]) if len(ventana) > 0 else 0
    
    # Guardar la nueva lectura en la ventana deslizante de 6 puntos
    ventana.append(valor_actual)
    
    # Jerarquía de evaluación (de mayor a menor severidad):
    
    # NIVEL 3: Peligro Crítico (Fuera de Especificación)
    if valor_actual < cfg["min"] or valor_actual > cfg["max"]:
        return {"estado": "Peligro", "valor": valor_actual}
    
    # NIVEL 1: Alerta por Salto Brusco (Control de Rango Móvil - MR)
    if mr >= cfg["mr_max"]:
        return {"estado": "Alerta Brusca", "valor": valor_actual}
    
    # NIVEL 2: Alerta por Tendencia Progresiva (6 lecturas consecutivas subiendo/bajando)
    if detectar_tendencia(ventana):
        return {"estado": "Alerta Tendencia", "valor": valor_actual}
    
    # ESTADO NORMAL
    return {"estado": "Normal", "valor": valor_actual}

@app.route('/telemetria', methods=['POST'])
def recibir_y_validar():
    # 1. Deserializa el JSON
    datos = request.get_json(silent=True)
    
    if not isinstance(datos, dict):
        return jsonify({"error": "El formato debe ser un objeto JSON válido"}), 400

    # 2. Define las llaves obligatorias y sus tipos de datos esperados en Python
    campos_esperados = {
        "bpm": (int, float),
        "spo2": (int, float),
        "temperature": (int, float)
    }

    # 3. Valida la existencia y el tipo de cada campo
    for campo, tipos_validos in campos_esperados.items():
        if campo not in datos:
            return jsonify({"error": f"Falta el campo obligatorio: '{campo}'"}), 400
        if isinstance(datos[campo], bool) or not isinstance(datos[campo], tipos_validos):
            return jsonify({"error": f"El campo '{campo}' tiene un tipo de dato inválido"}), 400

    # 4. Extraer variables (identifica al astronauta si envía "astro", sino usa "Astro 1")
    astro = datos.get("astro", "Astro 1")
    hr = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]

    # 5. Ejecutar análisis estadístico I-MR por variable
    res_bpm = evaluar_imr(astro, "bpm", hr)
    res_spo2 = evaluar_imr(astro, "spo2", spo2)
    res_temp = evaluar_imr(astro, "temperature", temperature)

    # 6. Formatear respuesta exacta con estado y valor detonante
    respuesta = {
        "astro": astro,
        "BPM": res_bpm,
        "SPO2": res_spo2,
        "Temperatura": res_temp
    }

    print(f"[{astro}] BPM: {res_bpm['estado']} ({hr}) | SPO2: {res_spo2['estado']} ({spo2}) | Temp: {res_temp['estado']} ({temperature})")

    return jsonify(respuesta), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)