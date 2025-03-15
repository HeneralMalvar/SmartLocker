import os
from asyncio import timeout
from tkinter import *
from PIL import Image, ImageTk
import numpy as np
import urllib.request
import mysql.connector
import face_recognition
import threading
import time
import datetime
import requests
from flask import request

from register import RegisterFace
import cv2
from testreg import RegisterFaces
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
import json
import csv
from tkinter import filedialog
import dlib
from imutils import face_utils
from scipy.spatial import distance
import serial

for port in ports:
    print(port.device)


class SmartLocker:
    def __init__(self, root):
        self.root = root

        # Main window
        self.root.geometry("1360x760+0+0")
        self.root.title("Smart Locker V1.0")
        self.root.resizable(False, False)
        base_dir = r"C:\Users\Charles\PycharmProjects\camServer\gui"

        bg_template = Image.open(os.path.join(base_dir, "bg-template.jpg")).resize(
            (1360, 760), Image.Resampling.LANCZOS
        )
        register_img = Image.open(os.path.join(base_dir, "register-button.png")).resize(
            (230, 50), Image.Resampling.LANCZOS
        )
        facerecognition_img = Image.open(os.path.join(base_dir, "faceregcognition-button.png")).resize(
            (220, 50), Image.Resampling.LANCZOS
        )
        database_img = Image.open(os.path.join(base_dir, "database-button.png")).resize(
            (230, 50), Image.Resampling.LANCZOS
        )

        # Convert to tkinter compatibility
        self.template_photo = ImageTk.PhotoImage(bg_template)
        self.register_image = ImageTk.PhotoImage(register_img)
        self.facerecognition_img = ImageTk.PhotoImage(facerecognition_img)
        self.database_img = ImageTk.PhotoImage(database_img)

        # Layout
        Label(self.root, image=self.template_photo).place(x=0, y=0, width=1360, height=760)
        Button(self.root, image=self.register_image, command=self.register_button).place(x=2, y=200, width=185, height=45)
        Button(self.root, image=self.facerecognition_img, command=self.toggle_live_feed).place(x=2, y=250, width=185, height=45)
        Button(self.root, image=self.database_img).place(x=2, y=300, width=185, height=45)
        self.recognize_name = StringVar()
        Entry(self.root, justify="center", textvariable=self.recognize_name, state="readonly").place(x=260, y=300, width=160, height=30)

        self.log_listbox = Listbox(self.root, font=("Arial", 12), bg="white", fg="black")
        self.log_listbox.place(x=900, y=185, width=400, height=200)
        scrollbar_listbox = Scrollbar(self.root)
        scrollbar_listbox.place(x=1280, y=190, height=192)
        self.log_listbox.config(yscrollcommand=scrollbar_listbox.set)
        scrollbar_listbox.config(command=self.log_listbox.yview)

        # Access Log Listbox
        self.access_log_listbox = Listbox(self.root, font=("Arial", 12), bg="white", fg="black")
        self.access_log_listbox.place(x=275, y=470, width=1000, height=200)
        scrollbar_access_log = Scrollbar(self.root)
        scrollbar_access_log.place(x=1255, y=470, height=200)
        self.access_log_listbox.config(yscrollcommand=scrollbar_access_log.set)
        scrollbar_access_log.config(command=self.access_log_listbox.yview)
        self.load_access_logs()
        self.export_csv_button = Button(self.root, text="Export Logs to CSV", font=("Arial", 12),
                                        bg="blue", fg="white", command=self.export_logs_to_csv)
        self.export_csv_button.place(x=900, y=620, width=200, height=40)

        self.url = 'http://172.20.10.3/cam-hi.jpg'
        self.ESP8266_IP = "172.20.10.4"
        self.ESP8266_PORT = 80
        self.ESP_URL = f"http://{self.ESP8266_IP}:{self.ESP8266_PORT}/command"

        # Threading events
        self.live_feed_event = threading.Event()
        self.fingerprint_event = threading.Event()  # Controls fingerprint verification
        self.fingerprint_thread_running = False
        self.live_feed_thread_running = False

        # Email configuration
        self.sender_email = "smartlockerv5@gmail.com"
        self.sender_password = "wvkchsukbbweyiui"
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

        # Instance variable to store fingerprint result
        self.idmo = None

    def send_email_notification(self, recipient_email, subject, body):
        """Send an email notification."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            self.log_list(f"Email notification sent to {recipient_email}")
        except Exception as e:
            self.log_list(f"Failed to send email: {e}")

    def send_command_to_esp(self, command):
        try:
            payload = {"command": command}
            headers = {"Content-Type": "application/json"}
            response = requests.post(self.ESP_URL, data=json.dumps(payload), headers=headers)
            if response.status_code == 200:
                print(f"ESP8266 Response: {response.text}")
            else:
                print(f"Error: ESP8266 returned status code {response.status_code}")
        except Exception as e:
            print(f"Failed to send command to ESP8266: {e}")

    def log_list(self, message):
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        self.log_listbox.insert(END, f"{timestamp} : {message}")
        self.log_listbox.yview(END)

    def load_from_db(self):
        try:
            connection = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="1234",
                database="new_schema"
            )
            cursor = connection.cursor()
            cursor.execute("SELECT name, face_encoding, email, contact, finger_id FROM registered_faces")
            encodings = [
                (name, np.frombuffer(encoding, dtype=np.float64), email, contact)
                for name, encoding, email, contact, finger_id in cursor.fetchall()]
            cursor.close()
            connection.close()
            return encodings
        except mysql.connector.Error as err:
            print(f"Error in Database:{err}")
            return []

    def recognize_face(self, face_image):
        try:
            rgb_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            face_encoding = face_recognition.face_encodings(rgb_face)
            if face_encoding:
                return face_encoding[0]
        except Exception as err:
            print(f"Error in Face Recognition: {err}")
            return None

    def check_url_availability(self, url):
        try:
            img_response = urllib.request.urlopen(url, timeout=2)
            return True
        except Exception as e:
            print(f"Error accessing URL: {e}")
            return False

    def register_button(self):
        RegisterFace(self)

    def stop_all(self, fingerprint_id=None):
        try:
            data = {"command": "stop_all"}
            if fingerprint_id:
                data["fingerprint_id"] = fingerprint_id
            response = requests.post("http://172.20.10.5:5000/send_command", json=data, timeout=10)
            time.sleep(2)
            if response.status_code == 200:
                self.log_list("Stop all command sent successfully.")
            else:
                self.log_list(f"Failed to send stop_all command: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.log_list(f"Error sending stop_all command: {e}")

    def verify_fingerprint(self, fingerprint_id=None):
        try:
            # Reset fingerprint result before a new scan
            self.idmo = None

            def request_thread():
                data = {"command": "verify_fingerprint"}
                if fingerprint_id:
                    data["fingerprint_id"] = fingerprint_id
                try:
                    response = requests.post("http://172.20.10.5:5000/send_command", json=data, timeout=10)
                    for _ in range(10):  # Try for ~10 seconds
                        time.sleep(1)
                        responses = requests.get("http://172.20.10.5:5000/get_responses").json()
                        self.idmo = responses.get("last_fingerprint_id")

                        # Break if a new fingerprint is detected
                        if self.idmo:
                            break
                except requests.exceptions.RequestException as e:
                    self.log_list(f"Error: {e}")

            thread = threading.Thread(target=request_thread, daemon=True)
            thread.start()
            thread.join()  # Wait until thread completes

            return self.idmo
        except Exception as e:
            self.log_list(f"Error during fingerprint verification: {e}")
            return None

    def eye_aspect_ratio(self, eye):
        """Calculate the Eye Aspect Ratio (EAR) to detect blinks."""
        A = distance.euclidean(eye[1], eye[5])
        B = distance.euclidean(eye[2], eye[4])
        C = distance.euclidean(eye[0], eye[3])
        ear = (A + B) / (2.0 * C)
        return ear

    def start_live_feed(self):
        """Captures live camera feed and performs face recognition with liveness detection."""
        encodings = self.load_from_db()

        if not self.check_url_availability(self.url):
            self.log_list("Error: Unable to connect to the camera feed.")
            return

        detector = dlib.get_frontal_face_detector()
        predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")  # Download from
        print(predictor)

        EAR_THRESHOLD = 0.3  # Below this value, the eyes are considered closed
        BLINK_CONSEC_FRAMES = 2  # Number of frames where blink should occur
        FRAME_COUNT = 0
        BLINK_COUNT = 0

        while self.live_feed_event.is_set():
            try:
                img_response = urllib.request.urlopen(self.url, timeout=5)
                img_np_array = np.array(bytearray(img_response.read()), dtype=np.uint8)
                frame = cv2.imdecode(img_np_array, cv2.IMREAD_COLOR)
                if frame is None:
                    self.log_list("Failed to fetch image. Retrying...")
                    continue

                frame_resized = cv2.resize(frame, (640, 480))
                gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
                rgb_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

                face_locations = face_recognition.face_locations(rgb_frame)
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                dlib_faces = detector(gray)

                for face, encoding in zip(face_locations, face_encodings):
                    matched_name = None

                    # Perform liveness detection (Blink detection)
                    for d_face in dlib_faces:
                        shape = predictor(gray, d_face)
                        shape = face_utils.shape_to_np(shape)

                        left_eye = shape[36:42]
                        right_eye = shape[42:48]
                        left_ear = self.eye_aspect_ratio(left_eye)
                        right_ear = self.eye_aspect_ratio(right_eye)
                        ear = (left_ear + right_ear) / 2.0

                        if ear < EAR_THRESHOLD:
                            FRAME_COUNT += 1
                        else:
                            if FRAME_COUNT >= BLINK_CONSEC_FRAMES:
                                self.log_list("Blink detected! Face is real.")
                                BLINK_COUNT += 1  # Increase blink count
                                self.log_list(f"Blink {BLINK_COUNT} detected")
                            FRAME_COUNT = 0  # Reset counter
                    if BLINK_COUNT < 1:  # Require at least 1 blinks to continue
                        self.log_list("Liveness check failed. No sufficient blinks detected.")
                        continue  # Skip recognition if no blinks are detected

                    # Face Recognition after confirming liveness
                    for name, db_encoding, email, contact in encodings:
                        face_distance = face_recognition.face_distance([db_encoding], encoding)
                        if face_distance[0] < 0.4:
                            matched_name = name
                            recipient_email = email
                            recipient_contact = contact
                            break

                    if matched_name:
                        self.log_list(f"Recognized: {matched_name}")
                        self.update_access_log(matched_name, "Granted")
                        self.send_command_to_esp(f"LCD_DISPLAY_ACCESS_GRANTED:{matched_name}")
                        self.recognize_name.set(matched_name)

                        if recipient_contact:
                            sms_message = f"Smart Locker Access Granted to {matched_name} on {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}."
                            self.send_sms_notification(recipient_contact, sms_message)

                        else:
                            self.log_list("No contact number found for the user")
                        if recipient_email:
                            subject = "Smart Locker Access Granted"
                            body = f"Access granted to {matched_name} on {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}."
                            self.send_email_notification(recipient_email, subject, body)
                            self.clear_values_and_restart()
                        else:
                            self.log_list(f"No email found for {matched_name}. Notification skipped.")
                    else:
                        self.log_list("Unregistered face detected")
                        self.send_command_to_esp("LCD_DISPLAY_ACCESS_DENIED")
                        self.recognize_name.set("Unknown")

            except Exception as e:
                self.log_list(f"Error in live feed: {e}")

        self.live_feed_event.clear()
        self.live_feed_thread_running = False
        self.log_list("Live feed has ended.")
    def clear_values_and_restart(self):
        """Clear all relevant values and restart the recognition process."""
        self.log_list("Clearing all values for the next recognition attempt.")
        self.idmo = None
        self.recognize_name.set("")
        self.face_recognition_result = None
        self.send_command_to_esp("LCD_DISPLAY_WAITING")
        time.sleep(2)
        self.live_feed_event.clear()
        self.fingerprint_event.clear()
        self.log_list("Restarting fingerprint verification...")
        self.toggle_live_feed()

    def fingerprint_verification_loop(self):
        while True:
            if not self.live_feed_event.is_set() and not self.fingerprint_event.is_set():
                # Reset stored fingerprint ID
                self.idmo = None

                # Request a new fingerprint verification
                idmo = self.verify_fingerprint()
                if not idmo:
                    self.log_list("Fingerprint verification failed. Retrying...")
                    time.sleep(1)
                    continue

                self.log_list("Fingerprint verified, proceeding with face recognition.")
                self.fingerprint_event.set()
                self.live_feed_event.set()

                # Start live feed if not already running
                if not self.live_feed_thread_running:
                    self.live_feed_thread_running = True
                    threading.Thread(target=self.start_live_feed_thread, daemon=True).start()

                # Wait until face recognition completes
                while self.live_feed_event.is_set():
                    time.sleep(1)

                # Reset fingerprint verification flag for next attempt
                self.log_list("Face recognition ended. Restarting fingerprint verification...")
                self.fingerprint_event.clear()
            else:
                time.sleep(1)

    def toggle_live_feed(self):
        """Starts the fingerprint verification process in a separate thread to prevent UI freezing."""
        # If a thread is already running, don't start another
        if self.fingerprint_thread_running:
            self.log_list("Fingerprint verification thread already running. No new thread started.")
            return

        if not self.live_feed_event.is_set():
            self.idmo = None
            self.log_list("Starting fingerprint verification thread...")
            self.fingerprint_thread_running = True
            threading.Thread(target=self.fingerprint_verification_loop, daemon=True).start()

    def start_live_feed_thread(self):
        """Start live feed in a new thread."""
        threading.Thread(target=self.start_live_feed, daemon=True).start()

    def load_access_logs(self):
        try:
            connection = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="1234",
                database="new_schema"
            )
            cursor = connection.cursor()
            cursor.execute("SELECT name, timestamp, status FROM access_logs ORDER BY timestamp DESC LIMIT 10")
            logs = cursor.fetchall()
            for log in reversed(logs):  # Show recent logs first
                self.access_log_listbox.insert(END, f"{log[1]} - {log[0]} - {log[2]}")
            cursor.close()
            connection.close()
        except mysql.connector.Error as err:
            self.log_list(f"Database Error: {err}")

    def update_access_log(self, name, status="Granted"):
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        log_entry = f"{timestamp} - {name} - {status}"

        # Insert log into the Listbox
        self.access_log_listbox.insert(END, log_entry)
        self.access_log_listbox.yview(END)  # Auto-scroll

        # Store log in MySQL database
        try:
            connection = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="1234",
                database="new_schema"
            )
            cursor = connection.cursor()
            sql = "INSERT INTO access_logs (name, timestamp, status) VALUES (%s, %s, %s)"
            cursor.execute(sql, (name, timestamp, status))
            connection.commit()
            cursor.close()
            connection.close()
        except mysql.connector.Error as err:
            self.log_list(f"Database Error: {err}")


    def export_logs_to_csv(self):
        try:
            # Open file dialog to select save location
            file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                     filetypes=[("CSV files", "*.csv")],
                                                     title="Save Access Logs")
            if not file_path:
                return  # User canceled the operation

            # Connect to MySQL database
            connection = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="1234",
                database="new_schema"
            )
            cursor = connection.cursor()
            cursor.execute("SELECT name, timestamp, status FROM access_logs ORDER BY timestamp DESC")
            logs = cursor.fetchall()

            # Write data to CSV
            with open(file_path, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Name", "Status"])  # CSV headers
                writer.writerows(logs)  # Write log data

            cursor.close()
            connection.close()

            self.log_list(f"Logs exported successfully to {file_path}")

        except mysql.connector.Error as err:
            self.log_list(f"Database Error: {err}")
        except Exception as e:
            self.log_list(f"Error: {e}")

    def send_sms_notification(self,phone_number,message):
        try:
            arduino_serial = serial.Serial("COM4",9600,timeout=1)
            time.sleep(2)
            sms_command = f"{phone_number},{message}\n"
            arduino_serial.write(sms_command.encode())
            self.log_list(f"SMS notification sent to {phone_number}")
            arduino_serial.close()
        except Exception as e:
            self.log_list(f"Failed to send SMS: {e}")

if __name__ == "__main__":
    root = Tk()
    app = SmartLocker(root)
    root.mainloop()
