from flask import Flask,jsonify,request
import mysql.connector
import numpy as np
from pyfingerprint.pyfingerprint import PyFingerprint
app = Flask(__name__)
db = mysql.connector.connect(
    host = "127.0.0.1",
    user = "root",
    password = "1234",
    database = "new_schema"
)
cursor = db.cursor()

@app.route('/register',methods=['POST'])
def register_fingerprint():
    data = request.json
    fingerprint_id = data['fingerprint_id']
    template = data['template']

    cursor.execute("INSERT INTO fingerprint_db (fingerprint_id,template) VALUES (%s,%s)",(fingerprint_id,template))
    db.commit()
    return jsonify({"Message": "Fingerprint is successfuly registered"})


@app.route('/verify', methods=['POST'])
def verify_fingerprint():
    data = request.json
    scanned_template = np.array([int(x, 16) for x in data["template"].split(",")])

    cursor.execute("SELECT fingerprint_id, template FROM users")
    for fingerprint_id, db_template in cursor.fetchall():
        db_template = np.array([int(x, 16) for x in db_template.split(",")])

        if np.array_equal(scanned_template, db_template):
            return jsonify({"message": f"Access Granted: ID {fingerprint_id}"}), 200

    return jsonify({"message": "Access Denied"}), 401
if __name__ == "__main__":
    app.run(host = "0.0.0.0", port=5000, debug = True)