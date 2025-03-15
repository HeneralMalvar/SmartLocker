import os.path
import cv2
import face_recognition
import mysql.connector
import numpy as np
import threading
import requests
import tkinter as tk
from tkinter import Toplevel, Label, Button, Entry, StringVar, Listbox,messagebox
from PIL import Image, ImageTk
import time

FLASK_SERVER_URL = "http://172.20.10.5:5000"  # Flask server URL

class RegisterFace:
    def __init__(self, parent):
        self.capture_event = threading.Event()
        self.parent = parent
        self.sample_count = 10
        self.current_samples = 0
        self.name = StringVar()
        self.email = StringVar()
        self.contact = StringVar()
        self.collected_encodings = []
        self.registration_data = {"face_encodings": None, "finger_id": None}

        # Create Registration Window
        self.window = Toplevel(parent)
        self.window.geometry("650x550")
        self.window.title("Register Face & Fingerprint")
        self.window.resizable(False, False)

        Label(self.window, text="Name:", font=("Arial", 14)).place(x=4, y=50)
        Entry(self.window, textvariable=self.name, font=("Arial", 14), width=20).place(x=70, y=50)

        Label(self.window, text="Email:", font=("Arial", 14)).place(x=4, y=80)
        Entry(self.window, textvariable=self.email, font=("Arial", 14), width=20).place(x=70, y=80)

        Label(self.window, text="Contact#:", font=("Arial", 14)).place(x=4, y=110)
        Entry(self.window, textvariable=self.contact, font=("Arial", 14), width=20).place(x=80, y=110)

        self.start_button = Button(self.window, text="Start Face Registration", command=self.start_registration)
        self.start_button.place(x=20, y=150)

        self.fingerprint_button = Button(self.window, text="Register Fingerprint", command=lambda: self.send_command("register_fingerprint"))
        self.fingerprint_button.place(x=200, y=150)

        self.store_button = Button(self.window, text="Store Data", command=self.store_registration_data, state=tk.DISABLED)
        self.store_button.place(x=400, y=150)

        Label(self.window, text="Fingerprint ID:").place(x=20, y=190)
        self.fingerprint_id_entry = Entry(self.window, width=10)
        self.fingerprint_id_entry.place(x=140, y=190)

        Button(self.window, text="Verify Fingerprint", command=lambda: self.send_command("verify_fingerprint")).place(x=20, y=220)
        Button(self.window, text="Delete Fingerprint", command=lambda: self.send_command("delete_fingerprint", self.fingerprint_id_entry.get())).place(x=20, y=260)
        Button(self.window, text="Sync Fingerprints", command=lambda: self.send_command("sync_fingerprints")).place(x=200, y=260)

        Label(self.window, text="Status Messages:").place(x=20, y=300)
        self.response_list = Listbox(self.window, width=80, height=10)
        self.response_list.place(x=20, y=330)

        self.existing_encodings = self.load_from_db()
        self.fetch_responses()

    def update_status(self, message):
        self.response_list.insert(0, message)

    def send_command(self, command, fingerprint_id=None):
        def request_thread():
            data = {"command": command}
            if fingerprint_id:
                data["fingerprint_id"] = fingerprint_id

            try:
                response = requests.post(f"{FLASK_SERVER_URL}/send_command", json=data, timeout=10)
                response_data = response.json()
                message = response_data.get("message", "No response message")

            except requests.exceptions.RequestException as e:
                message = f"Error: {e}"

            self.window.after(0, lambda: self.update_status(message))

        threading.Thread(target=request_thread, daemon=True).start()

    def register_fingerprint(self):
        def request_thread():
            self.window.after(0, lambda: self.fingerprint_button.config(state=tk.DISABLED))  # Disable button

            try:
                # Step 1: Request fingerprint registration
                response = requests.post(f"{FLASK_SERVER_URL}/register_fingerprint", timeout=10)
                response_data = response.json()

                if response.status_code != 200:
                    error_message = response_data.get("error", "Unknown error")
                    self.update_status(f"Fingerprint registration failed. Error: {error_message}")
                    return

                self.update_status("Waiting for fingerprint scan...")

                # Step 2: Wait for fingerprint ID to be updated (Polling Mechanism)
                for _ in range(10):  # Try for ~10 seconds
                    time.sleep(1)
                    responses = requests.get(f"{FLASK_SERVER_URL}/get_responses").json()
                    fingerprint_id = responses.get("last_fingerprint_id")

                    if fingerprint_id:
                        break  # Exit loop if ID is found

                if fingerprint_id:
                    self.registration_data["finger_id"] = fingerprint_id
                    print(fingerprint_id)

                    # Update UI field with received fingerprint ID
                    self.window.after(0, lambda: self.fingerprint_id_entry.delete(0, tk.END))
                    self.window.after(0, lambda: self.fingerprint_id_entry.insert(0, str(fingerprint_id)))
                    self.window.after(0, lambda: self.store_button.config(state="normal"))

                    self.update_status(f"Fingerprint registered with ID: {fingerprint_id}")
                else:
                    self.update_status("Fingerprint registration failed. No ID received.")

            except requests.exceptions.RequestException as e:
                self.update_status(f"Error: {e}")

            finally:
                self.window.after(0, lambda: self.fingerprint_button.config(state=tk.NORMAL))  # Re-enable button

        threading.Thread(target=request_thread, daemon=True).start()

    def enable_store_button(self):
        print(f"DEBUG: Face Encodings: {self.registration_data['face_encodings'] is not None}")
        print(f"DEBUG: Fingerprint ID: {self.registration_data['finger_id']}")

        if self.registration_data["face_encodings"] is not None and self.registration_data["finger_id"]:
            print("✅ Enabling Store Button!")  # Debugging
            self.store_button.config(state=tk.NORMAL)
        else:
            print("❌ Store Button Disabled - Missing Data")

    def store_registration_data(self):
        self.registration_data["name"] = self.name.get()
        self.registration_data["email"] = self.email.get()
        self.registration_data["contact"] = self.contact.get()

        # Check if encodings and fingerprint ID are available
        if len(self.collected_encodings) == 0 or not self.registration_data["finger_id"]:
            self.update_status("Incomplete registration, capture face and fingerprint first.")
            return

        try:
            connection = mysql.connector.connect(host="127.0.0.1", user="root", password="1234", database="new_schema")
            cursor = connection.cursor()

            query = """
            INSERT INTO registered_faces (name, face_encoding, email, contact, finger_id)
            VALUES (%s, %s, %s, %s, %s)
            """

            for encoding in self.collected_encodings:  # Store all face encodings
                cursor.execute(query, (
                    self.registration_data["name"],
                    encoding.tobytes(),  # Convert encoding to bytes
                    self.registration_data["email"],
                    self.registration_data["contact"],
                    self.registration_data["finger_id"]
                ))

            connection.commit()
            cursor.close()
            connection.close()

            self.update_status("Registration data stored successfully!")

        except mysql.connector.Error as err:
            self.update_status(f"Database error: {err}")

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

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                if face_encodings:
                    face_encoding = face_encodings[0]  # Get the first face encoding

                    if self.is_face_already_registered(face_encoding):
                        messagebox.showinfo("Warning", "Face already registered. Process stopped.", parent=self.window)
                        self.capture_event.clear()
                        return

                    self.collected_encodings.append(face_encoding)
                    self.current_samples += 1
                    self.update_status(f"Captured Sample {self.current_samples}/{self.sample_count}")

                    time.sleep(1.2)  # Pause for better registration
                    if self.current_samples >= self.sample_count:
                        self.capture_event.clear()
                        break

                cv2.imshow("Register Face", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            self.update_status(f"Error: {e}")

        finally:
            cap.release()
            cv2.destroyAllWindows()

            if len(self.collected_encodings) == self.sample_count:
                avg_encoding = np.mean(self.collected_encodings, axis=0)
                self.registration_data["face_encodings"] = avg_encoding

                print(f"DEBUG: Face encoding stored: {self.registration_data['face_encodings']}")  # Debugging

                self.update_status("Face registration complete!")
                self.enable_store_button()

    def is_face_already_registered(self, new_encoding):
        """Check if the given face encoding matches any registered encoding."""
        for name, db_encoding in self.existing_encodings:
            face_distance = face_recognition.face_distance([db_encoding], new_encoding)
            if face_distance[0] < 0.4:  # Match threshold
                messagebox.showinfo("Already Registered", f"This face is already registered as: {name},",parent=self.window)
                return True
        return False

    def load_from_db(self):
        """Load existing face encodings from MySQL database."""
        existing_encodings = []
        try:
            connection = mysql.connector.connect(host="127.0.0.1", user="root", password="1234", database="new_schema")
            cursor = connection.cursor()
            cursor.execute("SELECT name, face_encoding FROM registered_faces")  # Include 'name'
            rows = cursor.fetchall()
            for row in rows:
                name = row[0]  # Extract name
                encoding = np.frombuffer(row[1], dtype=np.float64)  # Convert BLOB to numpy array
                existing_encodings.append((name, encoding))  # Store as tuple (name, encoding)
            cursor.close()
            connection.close()
        except mysql.connector.Error as err:
            self.update_status(f"Database error: {err}")

        return existing_encodings

    def fetch_responses(self):
        try:
            response = requests.get(f"{FLASK_SERVER_URL}/get_responses", timeout=5)
            data = response.json()
            responses = data.get("responses", [])
            fingerprint_id = data.get("last_fingerprint_id")  # Extract fingerprint ID

            self.response_list.delete(0, tk.END)
            for res in reversed(responses):
                self.response_list.insert(tk.END, res)

            # ✅ If fingerprint ID is retrieved, store it and update UI
            if fingerprint_id and self.registration_data["finger_id"] is None:
                self.registration_data["finger_id"] = fingerprint_id

                # ✅ Update UI entry with fingerprint ID
                self.window.after(0, lambda: self.fingerprint_id_entry.delete(0, tk.END))
                self.window.after(0, lambda: self.fingerprint_id_entry.insert(0, str(fingerprint_id)))

                # ✅ Enable "Store Data" button if both face encoding & fingerprint ID are available
                self.window.after(0, self.enable_store_button)

                self.update_status(f"Fingerprint registered with ID: {fingerprint_id}")

        except requests.exceptions.RequestException as e:
            self.update_status(f"Error fetching responses: {e}")

        self.window.after(3000, self.fetch_responses)  # Fetch every 5 seconds


if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()
    RegisterFace(root)
    root.mainloop()
