from flask import Flask, request, jsonify
from collections import deque
import numpy as np

app = Flask(__name__)

# Tamaño de la ventana deslizante (búfer circular en RAM por variable)
VENTANA_MUESTRAS = 15

# Rangos clínicos estándares (mínimo, máximo) y umbral máximo de dispersión (desviación estándar)
PARAMETROS_ESTANDAR = {
    "bpm": {"min": 70.0, "max": 90.0, "std_max": 8.0},
    "spo2": {"min": 95.0, "max": 100.0, "std_max": 1.5},
    "temperature": {"min": 36.1, "max": 37.2, "std_max": 0.35}
}

# Búfer circular en RAM indexado por astronauta
buffer_telemetria = {}

def obtener_buffer_astro(astro):
    """Inicializa o recupera las ventanas deslizantes en RAM para un astronauta."""
    if astro not in buffer_telemetria:
        buffer_telemetria[astro] = {
            "bpm": deque(maxlen=VENTANA_MUESTRAS),
            "spo2": deque(maxlen=VENTANA_MUESTRAS),
            "temperature": deque(maxlen=VENTANA_MUESTRAS),
            "actividad": deque(maxlen=VENTANA_MUESTRAS)
        }
    return buffer_telemetria[astro]

def procesar_variable_numpy(ventana, valor_actual, reglas):
    """Inserta la muestra en el deque y calcula media y desviación estándar con NumPy."""
    ventana.append(float(valor_actual))
    
    arr = np.array(ventana, dtype=np.float64)
    media = float(np.round(np.mean(arr), 2))
    desv_std = float(np.round(np.std(arr), 2))
    
    # 1. Evaluación contra límites clínicos estándares
    if valor_actual < reglas["min"] or valor_actual > reglas["max"]:
        estado = "PELIGRO"
    # 2. Evaluación de inestabilidad estadística (cuando hay al menos 3 muestras)
    elif len(arr) >= 3 and desv_std > reglas["std_max"]:
        estado = "ALERTA"
    else:
        estado = "ESTABLE"
        
    return {
        "valor": valor_actual,
        "media": media,
        "std": desv_std,
        "estado": estado
    }

@app.route('/telemetria', methods=['POST'])
def recibir_telemetria():
    # 1. Deserialización segura (nunca lanza excepción ante tramas vacías o corruptas)
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"status": "ERROR", "detalle": "Payload JSON inválido o vacío"}), 400

    # 2. Validación estricta de llaves y tipos de datos
    esquema_obligatorio = {
        "astro": (str,),
        "bpm": (int, float),
        "spo2": (int, float),
        "temperature": (int, float),
        "actividad": (int,)
    }

    for llave, tipos_validos in esquema_obligatorio.items():
        if llave not in datos:
            return jsonify({"status": "ERROR", "detalle": f"Falta campo obligatorio: {llave}"}), 400
        valor = datos[llave]
        if isinstance(valor, bool) or not isinstance(valor, tipos_validos):
            return jsonify({"status": "ERROR", "detalle": f"Tipo inválido en '{llave}'"}), 400

    astro = datos["astro"].strip() or "Astro_Desconocido"
    buffers = obtener_buffer_astro(astro)

    # 3. Inserción en búfer circular y cálculo estadístico móvil con NumPy
    res_bpm = procesar_variable_numpy(buffers["bpm"], datos["bpm"], PARAMETROS_ESTANDAR["bpm"])
    res_spo2 = procesar_variable_numpy(buffers["spo2"], datos["spo2"], PARAMETROS_ESTANDAR["spo2"])
    res_temp = procesar_variable_numpy(buffers["temperature"], datos["temperature"], PARAMETROS_ESTANDAR["temperature"])
    buffers["actividad"].append(datos["actividad"])

    # 4. Consolidar estado global del traje (prioridad: PELIGRO > ALERTA > ESTABLE)
    estados_individuales = [res_bpm["estado"], res_spo2["estado"], res_temp["estado"]]
    if "PELIGRO" in estados_individuales:
        estado_global = "PELIGRO"
        activar_alerta_fisica = True
    elif "ALERTA" in estados_individuales:
        estado_global = "ALERTA"
        activar_alerta_fisica = True
    else:
        estado_global = "ESTABLE"
        activar_alerta_fisica = False

    # Log limpio en consola del Maestro
    print(
        f"[{astro} | Act:{datos['actividad']}] {estado_global} -> "
        f"BPM:{res_bpm['valor']} (μ:{res_bpm['media']}, σ:{res_bpm['std']}) | "
        f"SpO2:{res_spo2['valor']} (μ:{res_spo2['media']}, σ:{res_spo2['std']}) | "
        f"Temp:{res_temp['valor']} (μ:{res_temp['media']}, σ:{res_temp['std']})"
    )

    # 5. Respuesta JSON ligera y síncrona (200 OK) para el ESP32
    respuesta_esp = {
        "status": "OK",
        "astro": astro,
        "estado_global": estado_global,
        "alerta_fisica": activar_alerta_fisica,
        "analisis": {
            "bpm": res_bpm,
            "spo2": res_spo2,
            "temperature": res_temp
        }
    }

    return jsonify(respuesta_esp), 200

if __name__ == '__main__':
    print("🚀 Nodo Maestro Edge activo en 0.0.0.0:5000 (Red Local 2.4 GHz)")
    app.run(host='0.0.0.0', port=5000, threaded=True)