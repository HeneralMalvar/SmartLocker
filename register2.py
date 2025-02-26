import os.path
import cv2
import face_recognition
import mysql.connector
import numpy as np
import threading
import time
import requests
from tkinter import Toplevel, Label, Button, Entry, StringVar, messagebox
from PIL import Image, ImageTk


class RegisterFace:
    def __init__(self, parent):
        self.parent = parent
        self.capture_event = threading.Event()
        self.sample_count = 10  # Number of samples to capture
        self.current_samples = 0
        self.name = StringVar()
        self.email = StringVar()
        self.contact = StringVar()
        self.collected_encodings = []  # List to store face encodings during registration
        self.registration_data = []  # List to store all registration data
        self.fingerprint_id = None  # Initialize fingerprint_id to None
        self.blank_finger_ids = []
        # Create a new window for registration
        self.window = Toplevel(parent.root)
        self.window.geometry("600x400")
        self.window.title("Register Face")
        self.window.resizable(False, False)

        # UI Elements setup...
        Label(self.window, text="Name:", font=("Arial", 14)).place(x=4, y=50)
        self.name_entry = Entry(self.window, textvariable=self.name, font=("Arial", 14), width=20)
        self.name_entry.place(x=70, y=50)

        Label(self.window, text="Email: ", font=("Arial", 14)).place(x=4, y=80)
        self.email_entry = Entry(self.window, textvariable=self.email, font=("Arial", 14), width=20)
        self.email_entry.place(x=70, y=80)

        Label(self.window, text="Contact#: ", font=("Arial", 14)).place(x=4, y=110)
        self.contact_entry = Entry(self.window, textvariable=self.contact, font=("Arial", 14), width=20)
        self.contact_entry.place(x=80, y=110)

        self.info_label = Label(self.window, text="", font=("Arial", 8), fg="blue")
        self.info_label.place(x=350, y=100)

        self.start_button = Button(self.window, text="Start Registration", font=("Arial", 14),
                                   command=self.start_registration)
        self.start_button.place(x=0, y=150)

        self.register_button = Button(self.window, text="Register Fingerprint", command=self.register_fingerprint)
        self.register_button.place(x=200, y=150)

        self.store_button = Button(self.window, text="Store Registration Data", command=self.store_registration_data)
        self.store_button.place(x=400, y=150)

        self.face_cascade = cv2.CascadeClassifier('charles.xml')
        if self.face_cascade.empty():
            messagebox.showerror("Error", "Face cascade file not found.", parent=self.window)
            self.window.destroy()

        self.existing_encodings = self.load_from_db()

    def fetch_blank_finger_ids(self):
        """Fetch the pending finger_ids from the Flask server"""
        try:
            response = requests.get("http://127.0.0.1:5000/api/fingerprint_pending")
            if response.status_code == 200:
                data = response.json()
                print("Fetched Pending Fingerprint IDs:", data.get('finger_ids'))  # Print the received IDs
                self.blank_finger_ids = data.get('finger_ids', [])
            else:
                print(f"Failed to fetch pending finger_ids: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching blank finger IDs: {e}")

    def register_fingerprint(self):
        """Send request to ESP8266 server to register a fingerprint."""
        try:
            # Send the request to register fingerprint with no specific finger_id for new registration
            response = requests.post("http://192.168.1.58:5000/api/fingerprint", json={"register": True})

            if response.status_code == 200:
                data = response.json()


                # Check if the server returned the fingerprint ID after registration
                if data.get("status") == "pending":
                    finger_id = data.get("finger_id")
                    self.info_label.config(text=f"Fingerprint ID {finger_id} is pending registration. Please wait...")
                    # Start polling for registration confirmation
                    self.poll_fingerprint_registration(finger_id)
                else:
                    messagebox.showerror("Error", "Fingerprint registration failed.", parent=self.window)
            else:
                messagebox.showerror("Error", f"Server error: {response.status_code} - {response.text}", parent=self.window)

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to communicate with fingerprint server: {e}", parent=self.window)
            print(f"Request error: {e}")  # Debugging line to log request issues

    def poll_fingerprint_registration(self, finger_id):
        """Poll the server every few seconds to check if the fingerprint is fully registered."""
        attempts = 0
        while attempts < 10:
            attempts += 1
            time.sleep(5)  # Wait 5 seconds before rechecking

            try:
                response = requests.get(f"http://127.0.0.1:5000/api/fingerprint_pending")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "registered":
                        messagebox.showinfo("Success", f"Fingerprint ID {finger_id} registered successfully!", parent=self.window)
                        return  # Exit polling once registered
                    elif data.get("status") == "error":
                        messagebox.showerror("Error", "Fingerprint registration failed.", parent=self.window)
                        return
            except requests.exceptions.RequestException as e:
                print(f"Error during polling: {e}")
                continue

        messagebox.showinfo("Timeout", "Fingerprint registration took too long. Please try again later.", parent=self.window)
    def start_registration(self):
        if not self.name.get().strip():
            messagebox.showwarning("Warning", "Please enter a name for registration.", parent=self.window)
            return

        self.capture_event.set()
        self.current_samples = 0
        self.collected_encodings = []  # Clear encodings before starting
        threading.Thread(target=self.capture_samples, daemon=True).start()

    def capture_samples(self):
        cap = cv2.VideoCapture(0)  # Open the built-in webcam
        if not cap.isOpened():
            messagebox.showerror("Error", "Unable to access the laptop camera.", parent=self.window)
            return

        try:
            while self.capture_event.is_set() and self.current_samples < self.sample_count:
                ret, frame = cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)

                for (x, y, w, h) in faces:
                    face_crop = frame[y:y + h, x:x + w]
                    rgb_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                    face_encoding = face_recognition.face_encodings(rgb_face)

                    if face_encoding:
                        self.collected_encodings.append(face_encoding[0])
                        self.current_samples += 1
                        self.info_label.config(
                            text=f"Captured Sample {self.current_samples}/{self.sample_count}"
                        )
                        time.sleep(1.2)  # Pause for better registration
                        if self.current_samples >= self.sample_count:
                            self.info_label.config(text="Registration Complete!")
                            self.registration_data.append({
                                "name": self.name.get(),
                                "email": self.email_entry.get(),
                                "contact": self.contact_entry.get(),
                                "encodings": self.collected_encodings,
                                "fingerprint_id": self.fingerprint_id  # Ensure fingerprint_id is included
                            })
                            self.capture_event.clear()
                            return

                cv2.imshow("Register Face", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            self.info_label.config(text=f"Error: {e}")

        finally:
            cap.release()
            cv2.destroyAllWindows()

    def is_face_already_registered(self, new_encoding):
        """Check if the given face encoding matches any registered encoding."""
        for name, db_encoding in self.existing_encodings:
            face_distance = face_recognition.face_distance([db_encoding], new_encoding)
            if face_distance[0] < 0.4:  # Match threshold
                messagebox.showinfo("Already Registered", f"This face is already registered as: {name}",
                                    parent=self.window)
                return True
        return False

    def load_from_db(self):
        """Load all registered face encodings from the database."""
        try:
            connection = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="1234",
                database="new_schema"
            )
            cursor = connection.cursor()
            cursor.execute("SELECT name, face_encoding FROM registered_faces")
            encodings = [(name, np.frombuffer(encoding, dtype=np.float64)) for name, encoding in cursor.fetchall()]
            cursor.close()
            connection.close()
            return encodings
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error: {err}", parent=self.window)
            return []

    def store_registration_data(self):
        """Store all collected registration data into the database."""
        if not self.registration_data:
            messagebox.showwarning("Warning", "No registration data available to store.", parent=self.window)
            return

        try:
            connection = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="1234",
                database="new_schema"
            )
            cursor = connection.cursor()

            for data in self.registration_data:
                name = data["name"]
                email = data["email"]
                contact = data["contact"]
                fingerprint_id = data["fingerprint_id"]
                for encoding in data["encodings"]:
                    query = "INSERT INTO registered_faces (name, face_encoding, email, contact, finger_id) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(query, (name, encoding.tobytes(), email, contact, fingerprint_id))

            connection.commit()
            cursor.close()
            connection.close()
            messagebox.showinfo("Success", "Registration data successfully stored!",parent=self.window)
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error: {err}", parent=self.window)
