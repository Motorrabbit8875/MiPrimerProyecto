from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# Umbrales clínicos y saltos dinámicos condicionados por la ACTIVIDAD (0: Reposo, 1: Activo)
CONFIG_LIMITES = {
    0: {  # Reposo
        "bpm": {"min": 50, "max": 100, "salto_max": 20},
        "spo2": {"min": 92, "max": 100, "salto_max": 5},
        "temperature": {"min": 35.0, "max": 37.5, "salto_max": 0.8},
        "resp_rate": {"min": 12, "max": 20, "salto_max": 5},
        "bp_sys": {"min": 90, "max": 130, "salto_max": 20},
        "bp_dia": {"min": 60, "max": 85, "salto_max": 15},
        "radiation": {"min": 0.0, "max": 0.5, "salto_max": 0.2}
    },
    1: {  # Activo / Esfuerzo físico
        "bpm": {"min": 50, "max": 160, "salto_max": 35},
        "spo2": {"min": 90, "max": 100, "salto_max": 5},
        "temperature": {"min": 35.0, "max": 38.5, "salto_max": 1.2},
        "resp_rate": {"min": 12, "max": 32, "salto_max": 8},
        "bp_sys": {"min": 90, "max": 165, "salto_max": 25},
        "bp_dia": {"min": 60, "max": 95, "salto_max": 20},
        "radiation": {"min": 0.0, "max": 0.5, "salto_max": 0.2}
    }
}

# Memoria global en RAM por astronauta
estado_astronautas = {}

def inicializar_o_obtener_astro(astro_id):
    if astro_id not in estado_astronautas:
        estado_astronautas[astro_id] = {
            "enclavado": False,
            "tipo_alerta_activa": "desactivada",
            "mensaje_alerta": "Datos procesados correctamente",
            "historial": {
                "bpm": deque(maxlen=6),
                "spo2": deque(maxlen=6),
                "temperature": deque(maxlen=6),
                "resp_rate": deque(maxlen=6),
                "bp_sys": deque(maxlen=6),
                "bp_dia": deque(maxlen=6),
                "radiation": deque(maxlen=6)
            }
        }
    return estado_astronautas[astro_id]

@app.route('/telemetria', methods=['POST'])
def recibir_telemetria():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "Formato JSON inválido"}), 400

    astro = datos.get("astro", "Astro 1")
    ente = inicializar_o_obtener_astro(astro)

    # --- PASO 1: VERIFICAR SI EL OPERADOR ENVIÓ "ok" PARA DESENCLAVAR ---
    comando = str(datos.get("comando", "")).strip().lower()
    if comando == "ok":
        ente["enclavado"] = False
        ente["tipo_alerta_activa"] = "desactivada"
        ente["mensaje_alerta"] = "Datos procesados correctamente"
        for var in ente["historial"]:
            ente["historial"][var].clear()
        
        print(f"✅ [{astro}] OPERADOR CONFIRMó 'OK'. Alerta desenclavada.")
        return jsonify({
            "status": "OK",
            "astro": astro,
            "alerta": "desactivada",
            "mensaje": "Verificación completada. Alerta resuelta."
        }), 200

    # --- PASO 2: VALIDAR CAMPOS OBLIGATORIOS ---
    campos_requeridos = ["bpm", "spo2", "temperature", "resp_rate", "bp_sys", "bp_dia", "radiation", "actividad"]
    for campo in campos_requeridos:
        if campo not in datos:
            return jsonify({"error": f"Falta el campo obligatorio: '{campo}'"}), 400
        if not isinstance(datos[campo], (int, float)) or isinstance(datos[campo], bool):
            return jsonify({"error": f"El campo '{campo}' tiene un tipo de dato inválido"}), 400

    # Extracción de valores
    bpm = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]
    resp_rate = datos["resp_rate"]
    bp_sys = datos["bp_sys"]
    bp_dia = datos["bp_dia"]
    radiation = datos["radiation"]
    actividad = int(datos["actividad"]) # 0 o 1

    # Seleccionar perfil de límites según la actividad actual (0 o 1)
    perfil_limites = CONFIG_LIMITES.get(actividad, CONFIG_LIMITES[0])
    historial = ente["historial"]
    
    tipo_alerta_actual = "desactivada"
    mensaje_salida = "Datos procesados correctamente"

    valores_actuales = {
        "bpm": bpm,
        "spo2": spo2,
        "temperature": temperature,
        "resp_rate": resp_rate,
        "bp_sys": bp_sys,
        "bp_dia": bp_dia,
        "radiation": radiation
    }

    # --- PASO 3: EVALUAR LÍMITES Y CAMBIOS DINÁMICOS ---
    for variable, valor in valores_actuales.items():
        cfg = perfil_limites[variable]
        hist = historial[variable]

        # A. Revisar límite superado según perfil activo/reposo
        if valor < cfg["min"] or valor > cfg["max"]:
            tipo_alerta_actual = "limite_superado"
            mensaje_salida = f"Alerta crítica: {variable} fuera de rango [{actividad}] ({valor})"
            break

        # B. Revisar cambio drástico respecto al valor anterior
        if len(hist) > 0:
            ultimo_valor = hist[-1]
            cambio = abs(valor - ultimo_valor)
            if cambio > cfg["salto_max"]:
                tipo_alerta_actual = "cambio_drastico"
                mensaje_salida = f"Alerta dinámica: salto brusco en {variable} (Δ={cambio:.1f})"
                break

        # Agregar al historial en RAM
        hist.append(valor)

    # --- PASO 4: ENCLAVAR ALERTA SI HUBO ANOMALÍA ---
    if tipo_alerta_actual in ["limite_superado", "cambio_drastico"]:
        ente["enclavado"] = True
        ente["tipo_alerta_activa"] = tipo_alerta_actual
        ente["mensaje_alerta"] = mensaje_salida
        print(f"🚨 [{astro}] {mensaje_salida} -> ALERTA ENCLAVADA")

    # Si está enclavado, se repite la alerta hasta que llegue el "ok"
    alerta_a_enviar = ente["tipo_alerta_activa"] if ente["enclavado"] else "desactivada"
    mensaje_a_enviar = ente["mensaje_alerta"] if ente["enclavado"] else mensaje_salida

    print(f"[{astro}] Act:{actividad} | BPM:{bpm} | SpO2:{spo2}% | Temp:{temperature}°C | Resp:{resp_rate} | Sys/Dia:{bp_sys}/{bp_dia} | Rad:{radiation} ---> Alerta: {alerta_a_enviar}")

    return jsonify({
        "status": "OK",
        "astro": astro,
        "alerta": alerta_a_enviar,
        "mensaje": mensaje_a_enviar
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)