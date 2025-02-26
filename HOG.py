import os
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
        Button(self.root, image=self.register_image, command=self.register_button).place(x=2, y=200, width=185,
                                                                                         height=45)
        Button(self.root, image=self.facerecognition_img, command=self.toggle_live_feed).place(x=2, y=250, width=185,
                                                                                               height=45)
        Button(self.root, image=self.database_img).place(x=2, y=300, width=185, height=45)
        self.recognize_name = StringVar()
        Entry(self.root, justify="center", textvariable=self.recognize_name, state="readonly").place(x=260, y=300,
                                                                                                     width=160,
                                                                                                     height=30)

        self.log_listbox = Listbox(self.root, font=("Arial", 12), bg="white", fg="black")
        self.log_listbox.place(x=900, y=185, width=400, height=200)
        scrollbar_listbox = Scrollbar(self.root)
        scrollbar_listbox.place(x=1280, y=190, height=192)
        self.log_listbox.config(yscrollcommand=scrollbar_listbox.set)
        scrollbar_listbox.config(command=self.log_listbox.yview)

        self.url = 'http://192.168.100.228/cam-hi.jpg'
        self.ESP8266_IP = "192.168.100.229"
        self.ESP8266_PORT = 80
        self.ESP_URL = f"http://{self.ESP8266_IP}:{self.ESP8266_PORT}/command"

        # Threading event for live feed control
        self.live_feed_event = threading.Event()

        #Email configuration
        self.sender_email = "smartlockerv5@gmail.com"
        self.sender_password = "wvkchsukbbweyiui"
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_email_notification(self, recipient_email, subject, body):
        """Send an email notification."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            # Connect to the SMTP server
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Enable security
            server.login(self.sender_email, self.sender_password)

            # Send the email
            server.send_message(msg)
            server.quit()

            self.log_list(f"Email notification sent to {recipient_email}")
        except Exception as e:
            self.log_list(f"Failed to send email: {e}")

    def send_command_to_esp(self, command):
        try:
            # Construct the JSON payload
            payload = {
                "command": command
            }

            # Send a POST request with the 'application/json' content type
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
                for name, encoding, email, contact,finger_id in cursor.fetchall()]

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

    def verify_fingerprint(self, fingerprint_id=None):
        try:

            # This will store the result from the ESP8266
            idmo = None  # Initialize idmo as None to handle the case of no fingerprint

            def request_thread():
                nonlocal idmo
                data = {"command": "verify_fingerprint"}
                if fingerprint_id:
                    data["fingerprint_id"] = fingerprint_id

                try:
                    response = requests.post("http://192.168.100.226:5000/send_command", json=data, timeout=10)
                    for _ in range(10):  # Try for ~10 seconds
                        time.sleep(1)
                        responses = requests.get("http://192.168.100.226:5000/get_responses").json()
                        idmo = responses.get("last_fingerprint_id")  # Capture the fingerprint ID

                        if idmo:
                            break  # Exit loop if ID is found

                except requests.exceptions.RequestException as e:
                    self.log_list(f"Error: {e}")

            # Start the request thread and wait for the result
            thread = threading.Thread(target=request_thread, daemon=True)
            thread.start()
            thread.join()  # This ensures that the main thread waits until the request thread finishes

            return idmo  # Return the fingerprint ID (idmo)

        except Exception as e:
            self.log_list(f"Error during fingerprint verification: {e}")
            return None

    def start_live_feed(self):
        max_retries = 5  # Maximum number of retries for fetching the image
        retry_delay = 2  # Delay (in seconds) between retries
        encodings = self.load_from_db()

        if not self.check_url_availability(self.url):
            self.log_list("Error: Unable to connect to the camera feed.")
            return

        while self.live_feed_event.is_set():
            frame = None
            for attempt in range(max_retries):
                try:
                    # Attempt to fetch the image from the ESP camera
                    img_response = urllib.request.urlopen(self.url, timeout=5)
                    img_np_array = np.array(bytearray(img_response.read()), dtype=np.uint8)
                    frame = cv2.imdecode(img_np_array, cv2.IMREAD_COLOR)
                    break  # Exit retry loop if successful
                except (urllib.request.URLError, socket.timeout) as e:
                    self.log_list(f"Error fetching image (Attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)

            if frame is None:
                self.log_list("Failed to fetch image after multiple attempts. Check ESP module.")
                continue  # Skip further processing and retry fetching image

            # Process the frame for face recognition
            frame_resized = cv2.resize(frame, (640, 480))
            rgb_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

            # Detect faces in the frame
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for face_encoding in face_encodings:
                matched_name = None
                for name, db_encoding, email, contact in encodings:
                    face_distance = face_recognition.face_distance([db_encoding], face_encoding)
                    if face_distance[0] < 0.4:  # Match threshold
                        matched_name = name
                        recipient_email = email
                        recipient_contact = contact
                        break

                if matched_name:
                    self.log_list(f"Recognized: {matched_name}")
                    self.send_command_to_esp("LED_ON")
                    self.send_command_to_esp(f"LCD_DISPLAY_ACCESS_GRANTED:{matched_name}")
                    self.recognize_name.set(matched_name)

                    if recipient_email:
                        # Send dynamic email notification
                        subject = "Smart Locker Access Granted"
                        body = (
                            f"Access has been granted to {matched_name} on "
                            f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}."
                        )
                        self.send_email_notification(recipient_email, subject, body)
                        self.clear_values_and_restart()
                        self.toggle_live_feed()  # Recursively call the method to restart the process
                    else:
                        self.log_list(f"No email address found for {matched_name}. Notification skipped.")

                    # After recognizing a user, repeat the recognition process

                else:
                    self.log_list("Unregistered face detected")
                    self.send_command_to_esp("LED_OFF")
                    self.send_command_to_esp("LCD_DISPLAY_ACCESS_DENIED")
                    self.recognize_name.set("Unknown")

    def clear_values_and_restart(self):
        """Clear all relevant values and restart the recognition process."""
        # Clear all relevant values (e.g., fingerprint ID, face recognition name, etc.)
        self.log_list("Clearing all values for the next recognition attempt.")
        self.idmo = None  # Clear the fingerprint ID
        self.recognize_name.set("")  # Clear the recognized name
        self.face_recognition_result = None  # Clear face recognition result
        self.send_command_to_esp("LED_OFF")  # Turn off LED to reset
        self.send_command_to_esp("LCD_DISPLAY_WAITING")  # Optionally, display a waiting message on LCD

        # Optionally, you can introduce a brief wait before starting the next recognition attempt
        time.sleep(2)  # 2-second wait before starting the next recognition

        # Restart fingerprint verification

    def toggle_live_feed(self):
        if not self.live_feed_event.is_set():
            # Step 1: Verify fingerprint first
            idmo = self.verify_fingerprint()  # Ensure fingerprint is verified first
            print(idmo)

            if not idmo:  # If idmo is None, verification failed
                self.log_list("Fingerprint verification failed. Retrying...")
                time.sleep(1)  # Wait before retrying fingerprint verification
                return  # Exit the method and do not start the live feed

            # Step 2: If valid, proceed to face recognition
            self.log_list("Fingerprint verified, proceeding with face recognition.")

            self.live_feed_event.set()  # Start live feed
            self.log_list("Live feed started.")
            self.start_live_feed_thread()  # Start the live feed in a separate thread
        else:
            # Restart the live feed
            self.log_list("Live feed is restarting...")
            self.live_feed_event.clear()  # Clear the event (stop the current feed)
            self.toggle_live_feed()

    def start_live_feed_thread(self):
        live_feed_thread = threading.Thread(target=self.start_live_feed, daemon=True)
        live_feed_thread.start()


if __name__ == "__main__":
    root = Tk()
    app = SmartLocker(root)
    root.mainloop()
