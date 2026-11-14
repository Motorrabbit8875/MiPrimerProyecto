from flask import Flask, request

app = Flask(__name__)

@app.route('/telemetria', methods=['POST'])
def recibir_json_crudo():
    
    # Esto atrapa el cuerpo de la petición HTTP exactamente como texto plano,
    # sin deserializarlo a un diccionario de Python.
    json_crudo_texto = request.get_data(as_text=True)
    
    # Imprimes el string crudo en tu consola para verificar que llegó bien
    print(f"Texto JSON recibido sin deserializar: {json_crudo_texto}")
    
    # Le respondes al ESP32 que todo bien
    return "Recibido crudo", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)