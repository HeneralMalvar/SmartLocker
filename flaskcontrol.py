from flask import Flask, request, jsonify
import requests
import mysql.connector
import json  # ✅ Added for safe JSON parsing

ESP8266_URL = "http://192.168.100.229/command"  # Update if needed

app = Flask(__name__)

# ✅ MySQL Configuration
db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "1234",
    "database": "new_schema"
}

# ✅ Store last registered fingerprint ID
server_responses = []
fingerprint_id_global = None

# 🔹 Helper function to communicate with ESP8266
def send_command_to_esp(command, fingerprint_id=None):
    global fingerprint_id_global

    try:
        payload = {"command": command}
        if fingerprint_id is not None:
            payload["fingerprint_id"] = fingerprint_id

        print(f"📡 Sending to ESP8266: {payload}")  # Debugging
        response = requests.post(ESP8266_URL, json=payload, timeout=5)
        response_data = response.json()

        print(f"📩 Response from ESP8266: {response_data}")  # Debugging

        # ✅ Update global fingerprint ID if received
        if "fingerprint_id" in response_data:
            fingerprint_id_global = response_data["fingerprint_id"]

        return response_data

    except requests.exceptions.RequestException as e:
        print(f"❌ ESP8266 Connection Failed: {e}")
        return {"error": f"ESP8266 Connection Failed: {e}"}

    except ValueError:
        print("❌ Invalid JSON response from ESP8266")
        return {"error": "Invalid JSON response"}

# ✅ General command handler
@app.route('/send_command', methods=['POST'])
def send_command():
    try:
        data = request.json
        command = data.get("command", "")
        fingerprint_id = data.get("fingerprint_id")

        print(f"📥 Received Command: {command}, Fingerprint ID: {fingerprint_id}")

        response = send_command_to_esp(command, fingerprint_id)
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/register_fingerprint', methods=['POST'])
def register_fingerprint():
    global fingerprint_id_global

    response = send_command_to_esp("register_fingerprint")
    fingerprint_id = response.get("fingerprint_id")

    if fingerprint_id:
        fingerprint_id_global = fingerprint_id  # ✅ Store globally
        return jsonify({"message": "Fingerprint registered!", "fingerprint_id": fingerprint_id}), 200
    else:
        return jsonify({"error": "Fingerprint ID not found"}), 500
# ✅ Store server responses for debugging
@app.route('/fingerprint_response', methods=['POST'])
def fingerprint_response():
    global fingerprint_id_global

    try:
        data = request.get_json()
        print(f"📩 ESP8266 Response Received: {data}")  # Debugging

        # Store response in the list
        server_responses.append(data)

        # Extract fingerprint_id if present
        fingerprint_id = data.get("fingerprint_id")
        if fingerprint_id is not None:
            fingerprint_id_global = fingerprint_id  # Store in global variable
            print(f"✅ Stored Fingerprint ID: {fingerprint_id_global}")  # Print it

        return jsonify({"message": "Response received"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Fetch stored responses
@app.route('/get_responses', methods=['GET'])
def get_responses():
    return jsonify({"responses": server_responses, "last_fingerprint_id": fingerprint_id_global})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)
