from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# Límites clínicos (I) y umbral de salto brusco (40% de la amplitud del rango normal)
CONFIG_IMR = {
    "bpm": {"min": 70, "max": 90, "mr_max": 15},          # Ejemplo: 70 -> 85 (salto de 15)
    "spo2": {"min": 95, "max": 100, "mr_max": 2},         # 40% de 5% = 2% de salto
    "temperature": {"min": 36.1, "max": 37.2, "mr_max": 0.4} # Ejemplo: 36.3 -> 36.7 (salto de 0.4)
}

# Memoria por astronauta: guarda historial y estado de bloqueo por variación brusca
estado_entes = {}

def inicializar_ente(astro):
    if astro not in estado_entes:
        estado_entes[astro] = {
            "bloqueado": False,
            "mensaje_bloqueo": "",
            "historial": {
                "bpm": deque(maxlen=6),
                "spo2": deque(maxlen=6),
                "temperature": deque(maxlen=6)
            }
        }

def detectar_tendencia(valores):
    if len(valores) < 6:
        return False
    lista = list(valores)
    return all(lista[i] < lista[i + 1] for i in range(5)) or all(lista[i] > lista[i + 1] for i in range(5))

def evaluar_imr(astro, variable, valor_actual):
    cfg = CONFIG_IMR[variable]
    ventana = estado_entes[astro]["historial"][variable]
    
    mr = abs(valor_actual - ventana[-1]) if len(ventana) > 0 else 0
    ventana.append(valor_actual)
    
    # 1. Nivel 3: Peligro Crítico (Fuera de rango estándar)
    if valor_actual < cfg["min"] or valor_actual > cfg["max"]:
        return {"estado": "Peligro", "valor": valor_actual, "brusco": False}
    
    # 2. Nivel 1: Salto Brusco (Detona bloqueo de operador)
    if mr >= cfg["mr_max"]:
        return {"estado": "Alerta Brusca", "valor": valor_actual, "brusco": True}
    
    # 3. Nivel 2: Tendencia Progresiva (6 lecturas consecutivas)
    if detectar_tendencia(ventana):
        return {"estado": "Alerta Tendencia", "valor": valor_actual, "brusco": False}
    
    return {"estado": "Normal", "valor": valor_actual, "brusco": False}

@app.route('/telemetria', methods=['POST'])
def recibir_y_validar():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "El formato debe ser un objeto JSON válido"}), 400

    astro = datos.get("astro", "Astro 1")
    inicializar_ente(astro)
    ente = estado_entes[astro]

    # --- PASO A: VERIFICAR SI EL OPERADOR ENVIÓ "ok" DESDE LA ESP32 ---
    comando = str(datos.get("comando", "")).strip().lower()
    if comando == "ok":
        ente["bloqueado"] = False
        ente["mensaje_bloqueo"] = ""
        # Limpiamos el historial anterior para que el nuevo valor no dispare otro salto falso
        for var in ente["historial"]:
            ente["historial"][var].clear()
        
        print(f"✅ [{astro}] OPERADOR CONFIRMÓ 'OK'. Sistema desbloqueado y reanudando lecturas.")
        return jsonify({
            "astro": astro,
            "estado": "REANUDADO",
            "mensaje": "Operador verificado. Reanudando toma de valores."
        }), 200

    # --- PASO B: SI ESTÁ BLOQUEADO POR VARIACIÓN BRUSCA, IGNORAR LECTURAS Y MANTENER AVISO ---
    if ente["bloqueado"]:
        print(f"🔒 [{astro}] BLOQUEADO - Esperando 'ok' del operador...")
        return jsonify({
            "astro": astro,
            "estado": "BLOQUEADO",
            "mensaje": "Alerta variacion brusca, favor de revisar operador"
        }), 200

    # --- PASO C: VALIDAR TIPOS DE DATOS DE LOS SENSORES ---
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

    hr = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]

    # --- PASO D: EVALUAR MÉTODO I-MR ---
    res_bpm = evaluar_imr(astro, "bpm", hr)
    res_spo2 = evaluar_imr(astro, "spo2", spo2)
    res_temp = evaluar_imr(astro, "temperature", temperature)

    # Revisar si CUALQUIERA de las 3 variables tuvo un cambio brusco
    if res_bpm["brusco"] or res_spo2["brusco"] or res_temp["brusco"]:
        ente["bloqueado"] = True
        aviso = "Alerta variacion brusca, favor de revisar operador"
        print(f"🚨 [{astro}] {aviso} -> BPM:{hr} | SpO2:{spo2} | Temp:{temperature}")
        return jsonify({
            "astro": astro,
            "estado": "BLOQUEADO",
            "mensaje": aviso
        }), 200

    # Si no hubo salto brusco, devolver estado normal / tendencia / peligro
    respuesta = {
        "astro": astro,
        "BPM": {"estado": res_bpm["estado"], "valor": res_bpm["valor"]},
        "SPO2": {"estado": res_spo2["estado"], "valor": res_spo2["valor"]},
        "Temperatura": {"estado": res_temp["estado"], "valor": res_temp["valor"]}
    }

    print(f"[{astro}] BPM: {res_bpm['estado']} ({hr}) | SPO2: {res_spo2['estado']} ({spo2}) | Temp: {res_temp['estado']} ({temperature})")
    return jsonify(respuesta), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)