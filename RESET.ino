#include <ESP8266WiFi.h>
#include <Adafruit_Fingerprint.h>
#include <SoftwareSerial.h>

SoftwareSerial mySerial(D1, D2);  // RX, TX
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

void setup() {
    Serial.begin(115200);

    finger.begin(57600);
    if (finger.verifyPassword()) {
        Serial.println("Fingerprint sensor found!");
    } else {
        Serial.println("Fingerprint sensor NOT detected!");
        while (1) { delay(1); }
    }

    Serial.println("⚠️ WARNING: This will delete all fingerprints from the sensor.");
    Serial.println("Type 'DELETE' in the Serial Monitor to confirm.");

    while (!Serial.available());  // Wait for user input

    String input = Serial.readStringUntil('\n');  // Read user input
    input.trim();

    if (input == "DELETE") {
        clearFingerprintDatabase();
    } else {
        Serial.println("Deletion Canceled. Restart the device to try again.");
    }
}

void loop() {
    // Do nothing after clearing the database
}

void clearFingerprintDatabase() {
    Serial.println("Deleting all fingerprints...");

    if (finger.emptyDatabase() == FINGERPRINT_OK) {
        Serial.println("✅ All fingerprints deleted successfully!");
    } else {
        Serial.println("❌ Failed to delete fingerprints!");
    }
}
