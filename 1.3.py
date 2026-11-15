from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# Configuración de límites clínicos y saltos drásticos permitidos (Control I-MR)
CONFIG_LIMITES = {
    "bpm": {"min": 50, "max": 120, "salto_max": 25},
    "spo2": {"min": 90, "max": 100, "salto_max": 5},
    "temperature": {"min": 35.0, "max": 38.5, "salto_max": 1.0},
    "actividad": {"min": 0, "max": 1, "salto_max": 1}
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
                "actividad": deque(maxlen=6)
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
        
        print(f"✅ [{astro}] OPERADOR CONFIRMÓ 'OK'. Alerta desenclavada y sistema normalizado.")
        return jsonify({
            "status": "OK",
            "astro": astro,
            "alerta": "desactivada",
            "mensaje": "Verificación completada. Alerta resuelta."
        }), 200

    # --- PASO 2: VALIDAR CAMPOS (EL SISTEMA NUNCA DEJA DE FUNCIONAR) ---
    campos_requeridos = ["bpm", "spo2", "temperature", "actividad"]
    for campo in campos_requeridos:
        if campo not in datos:
            return jsonify({"error": f"Falta el campo obligatorio: '{campo}'"}), 400
        if not isinstance(datos[campo], (int, float)) or isinstance(datos[campo], bool):
            return jsonify({"error": f"El campo '{campo}' tiene un tipo de dato inválido"}), 400

    bpm = datos["bpm"]
    spo2 = datos["spo2"]
    temperature = datos["temperature"]
    actividad = datos["actividad"]

    historial = ente["historial"]
    
    # Evaluar la lectura actual de los sensores
    tipo_alerta_actual = "desactivada"
    mensaje_salida = "Datos procesados correctamente"

    valores_actuales = {
        "bpm": bpm,
        "spo2": spo2,
        "temperature": temperature,
        "actividad": actividad
    }

    for variable, valor in valores_actuales.items():
        cfg = CONFIG_LIMITES[variable]
        hist = historial[variable]

        # A. Revisar límite superado
        if valor < cfg["min"] or valor > cfg["max"]:
            tipo_alerta_actual = "limite_superado"
            mensaje_salida = f"Alerta crítica: {variable} fuera de rango ({valor})"
            break

        # B. Revisar cambio drástico respecto al valor anterior inmediato
        if len(hist) > 0:
            ultimo_valor = hist[-1]
            cambio = abs(valor - ultimo_valor)
            if cambio > cfg["salto_max"]:
                tipo_alerta_actual = "cambio_drastico"
                mensaje_salida = f"Alerta dinámica: salto brusco en {variable} (Δ={cambio:.1f})"
                break

        # Agregar al historial en RAM
        hist.append(valor)

    # --- PASO 3: SI HUBO ANOMALÍA, ENCLAVAR LA ALERTA ---
    if tipo_alerta_actual in ["limite_superado", "cambio_drastico"]:
        ente["enclavado"] = True
        ente["tipo_alerta_activa"] = tipo_alerta_actual
        ente["mensaje_alerta"] = mensaje_salida
        print(f"🚨 [{astro}] {mensaje_salida} -> ALERTA ENCLAVADA")

    # --- PASO 4: DECIDIR QUÉ ALERTA MANDAR DE REGRESO ---
    # Si el astronauta está enclavado, se sigue mandando la alerta activa en cada ciclo
    # hasta que llegue el "ok" del operador, sin importar si los datos nuevos ya se estabilizaron.
    alerta_a_enviar = ente["tipo_alerta_activa"] if ente["enclavado"] else "desactivada"
    mensaje_a_enviar = ente["mensaje_alerta"] if ente["enclavado"] else mensaje_salida

    print(f"[{astro}] BPM: {bpm} | SpO2: {spo2} | Temp: {temperature} ---> Alerta en respuesta: {alerta_a_enviar}")

    return jsonify({
        "status": "OK",
        "astro": astro,
        "alerta": alerta_a_enviar,
        "mensaje": mensaje_a_enviar
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)