#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>
#include <Adafruit_Fingerprint.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <SoftwareSerial.h>
#include <LiquidCrystal_PCF8574.h>  // I2C LCD library
#include <Adafruit_Fingerprint.h>
#define SDA_PIN D5
#define SCL_PIN D6
#define RELAY_PIN D4
#define RESET_BUTTON D3

LiquidCrystal_PCF8574 lcd(0x27); 
 
SoftwareSerial mySerial(D1, D2);  // RX, TX for R307
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

const char* ssid = "leviwifi";
const char* password = "levi121423";
ESP8266WebServer server(80);

void connectWiFi() {
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.print(".");
    }
    Serial.println("\n✅ Connected to WiFi!");
  
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
}

int getNextFingerprintID() {
    if (finger.getTemplateCount() != FINGERPRINT_OK) {
        Serial.println("❌ Failed to get fingerprint count!");
        return -1;
    }

    int count = finger.templateCount;
    if (count >= 127) {
        Serial.println("❌ No available slots!");
        return -1;
    }

    return count + 1;  // Assign the next available ID
}
void sendToFlask(String jsonData) {
    WiFiClient client;
    HTTPClient http;
    
    String serverURL = "http://192.168.1.42:5000/fingerprint_response";  // Flask endpoint for responses
    http.begin(client, serverURL);
    http.addHeader("Content-Type", "application/json");

    Serial.println("📡 Sending fingerprint response to Flask server...");
    int httpResponseCode = http.POST(jsonData);

    if (httpResponseCode > 0) {
        Serial.printf("✅ Flask Server Response: %d\n", httpResponseCode);
        Serial.println(http.getString());
    } else {
        Serial.printf("❌ Failed to send response! HTTP Error: %s\n", http.errorToString(httpResponseCode).c_str());
    }

    http.end();
}

void sendToServer(String jsonData) {
    WiFiClient client;
    HTTPClient http;

    String serverURL = "http://192.168.1.42:5000/sync_fingerprints";  // Replace with your Flask server IP
    http.begin(client, serverURL);
    http.addHeader("Content-Type", "application/json");

    Serial.println("📡 Sending fingerprint sync data to server...");
    int httpResponseCode = http.POST(jsonData);

    if (httpResponseCode > 0) {
        Serial.printf("✅ Server Response: %d\n", httpResponseCode);
        Serial.println(http.getString());
    } else {
        Serial.printf("❌ Failed to send data! HTTP Error: %s\n", http.errorToString(httpResponseCode).c_str());
    }

    http.end();
}

void syncFingerprints() {
    if (finger.getTemplateCount() != FINGERPRINT_OK) {
        Serial.println("❌ Failed to get fingerprint count!");
        return;
    }

    int totalFingerprints = finger.templateCount;
    if (totalFingerprints <= 0) {
        Serial.println("❌ No fingerprints stored.");
        return;
    }

    Serial.printf("🔄 Syncing %d stored fingerprints...\n", totalFingerprints);

    DynamicJsonDocument doc(1024);
    JsonArray fingerprint_ids = doc.createNestedArray("fingerprint_id");

    for (int i = 1; i <= totalFingerprints; i++) {  
        if (finger.loadModel(i) == FINGERPRINT_OK) {
            fingerprint_ids.add(i);
            Serial.printf("✔ Found Fingerprint ID: %d\n", i);
        } else {
            Serial.printf("⚠ Skipping invalid fingerprint ID: %d\n", i);
        }
    }

    String output;
    serializeJson(doc, output);
    Serial.println("📡 Sending synchronized fingerprints to Flask server...");
    sendToServer(output);

    // ✅ FIX: Declare response before using it
    DynamicJsonDocument response(128);
    response["message"] = "Fingerprints synchronized successfully!";
    sendResponse(response);
}

void handleCommand() {
    if (server.hasArg("plain")) {
        DynamicJsonDocument doc(256);
        deserializeJson(doc, server.arg("plain"));

        String command = doc["command"].as<String>();

        Serial.print("📩 Received command: ");
        Serial.println(command);

        DynamicJsonDocument response(128);  // Declare response here

        if (command == "register_fingerprint") {
            Serial.println("👆 Waiting for finger placement...");
            response["message"] = "Place your finger to register.";
            sendResponse(response);

            while (finger.getImage() != FINGERPRINT_OK) {
                delay(200);
            }

            Serial.println("✅ Finger detected. Capturing first image...");
            if (finger.image2Tz(1) != FINGERPRINT_OK) {
                Serial.println("❌ First scan failed!");
                response["error"] = "First scan failed!";
                sendResponse(response);
                return;
            }

            Serial.println("✔ First scan successful! Remove your finger...");
            response["message"] = "First scan complete. Remove your finger.";
            sendResponse(response);

            while (finger.getImage() == FINGERPRINT_OK) {
                delay(200);
            }

            Serial.println("💡 Place your finger again for the second scan...");
            response["message"] = "Place your finger for the second scan.";
            sendResponse(response);

            while (finger.getImage() != FINGERPRINT_OK) {
                delay(200);
            }

            Serial.println("✅ Finger detected. Capturing second image...");
            if (finger.image2Tz(2) != FINGERPRINT_OK) {
                Serial.println("❌ Second scan failed!");
                response["error"] = "Second scan failed!";
                sendResponse(response);
                return;
            }

            if (finger.createModel() != FINGERPRINT_OK) {
                Serial.println("❌ Could not create fingerprint model!");
                response["error"] = "Could not create fingerprint model!";
                sendResponse(response);
                return;
            }

            // **CHECK FOR DUPLICATE AFTER MODEL CREATION**
            if (finger.fingerFastSearch() == FINGERPRINT_OK) {
                Serial.printf("❌ Fingerprint already registered! ID: %d\n", finger.fingerID);
                response["error"] = "Fingerprint already registered!";
                sendResponse(response);
                return;
            }

            int newID = getNextFingerprintID();
            if (newID == -1) {
                response["error"] = "No free slots available!";
                sendResponse(response);
                return;
            }

            if (finger.storeModel(newID) == FINGERPRINT_OK) {
                Serial.printf("🎉 Fingerprint stored successfully! ID: %d\n", newID);
                response["message"] = "Fingerprint stored successfully!";
                response["fingerprint_id"] = newID;
                sendResponse(response);
                DynamicJsonDocument flaskData(128);
                flaskData["fingerprint_id"] = newID;

                String flaskJson;
                serializeJson(flaskData, flaskJson);
                sendToFlask(flaskJson);
            } else {
                Serial.println("❌ Failed to store fingerprint!");
                response["error"] = "Failed to store fingerprint!";
            }

            sendResponse(response);
        }

        else if (command == "verify_fingerprint") {
            Serial.println("💡 Place your finger on the scanner for verification...");
            response["message"] = "Waiting for fingerprint verification...";
            sendResponse(response);

            while (finger.getImage() != FINGERPRINT_OK) {
                delay(200);
            }

            Serial.println("✅ Fingerprint detected, processing...");
            if (finger.image2Tz(1) == FINGERPRINT_OK) {
                if (finger.fingerFastSearch() == FINGERPRINT_OK) {
                    response["message"] = "Fingerprint matched!";
                    response["fingerprint_id"] = finger.fingerID;
                    Serial.printf("✔ Match found! ID: %d\n", finger.fingerID);
                } else {
                    response["error"] = "No match found!";
                    Serial.println("❌ No fingerprint match.");
                }
            } else {
                response["error"] = "Failed to process fingerprint!";
            }
            sendResponse(response);
        } 

        else if (command == "delete_fingerprint") {
            if (!doc.containsKey("fingerprint_id")) {
                response["error"] = "Missing fingerprint ID!";
                sendResponse(response);
                return;
            }

            int fingerID = doc["fingerprint_id"].as<int>();

            Serial.printf("🗑 Deleting fingerprint ID: %d...\n", fingerID);

            if (finger.deleteModel(fingerID) == FINGERPRINT_OK) {
                Serial.printf("✅ Fingerprint ID %d deleted successfully!\n", fingerID);
                response["message"] = "Fingerprint deleted successfully!";
            } else {
                Serial.printf("❌ Failed to delete fingerprint ID %d!\n", fingerID);
                response["error"] = "Failed to delete fingerprint!";
            }

            sendResponse(response);
        }
        else if (command == "sync_fingerprints"){
            syncFingerprints();
            return;
        }
       else if (command.startsWith("LCD_DISPLAY_ACCESS_GRANTED:")) {
            String name = command.substring(26);  // Extract name from the command
            Serial.println("ACCESS GRANTED for " + name);
            
            // Display the "Access Granted" message on the LCD
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Access Granted");
            lcd.setCursor(0, 1);
            lcd.print(name);  // Print the name on the second line

            digitalWrite(RELAY_PIN, HIGH);
            
            // Turn on the backlight and the LED
            lcd.setBacklight(HIGH);
            digitalWrite(LED_BUILTIN, LOW);  // Turn on LED
            delay(5000);
            lcd.clear();

            delay(2000); // Keep the message for 2 seconds
            lcd.setBacklight(LOW); // Turn off backlight after delay
            digitalWrite(LED_BUILTIN, HIGH); // Turn off LED
        } 
        else if (command == "LCD_DISPLAY_ACCESS_DENIED") {
            Serial.println("ACCESS DENIED");
            
            // Display the "Access Denied" message on the LCD
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Access Denied");
            
            // Turn on the backlight and the LED
            lcd.setBacklight(HIGH);
            digitalWrite(LED_BUILTIN, HIGH);  // Keep the LED off

            delay(2000); // Keep the message for 2 seconds
            lcd.setBacklight(LOW); // Turn off backlight after delay
            lcd.clear();
        } 
        else {
            response["error"] = "Unknown command";
            sendResponse(response);
        }
    } else {
        server.send(400, "application/json", "{\"error\": \"Invalid request\"}");
    }
}
void sendResponse(DynamicJsonDocument &response) {
    String responseString;
    serializeJson(response, responseString);
    server.send(200, "application/json", responseString);

    // ✅ Send response to Flask server
    sendToFlask(responseString);
}


void setup() {
    Serial.begin(115200);
    mySerial.begin(57600);
    finger.begin(57600);
    Serial.println("🔍 Waiting for sensor to initialize...");
    delay(2000);  // Allow time for sensor startup

    Serial.println("🔍 Checking stored fingerprints...");
    if (finger.getTemplateCount() == FINGERPRINT_OK) {
        Serial.printf("✔ Found %d stored fingerprints.\n", finger.templateCount);
    } else {
        Serial.println("❌ Failed to get fingerprint count!");
    }
    Serial.println("🔍 Testing Fingerprint Sensor...");
    if (finger.verifyPassword()) {
        Serial.println("✅ Fingerprint sensor detected!");
    } else {
        Serial.println("❌ Fingerprint sensor not responding! Check wiring.");
    }
    Wire.begin(SDA_PIN,SCL_PIN);
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, LOW);
    lcd.begin(16, 2);  // Initialize the LCD, specify the number of columns and rows
    lcd.setBacklight(LOW); // Turn off backlight initially

    pinMode(LED_BUILTIN, OUTPUT);  // Assume LED is connected to pin D1
    pinMode(RESET_BUTTON, INPUT);
    digitalWrite(LED_BUILTIN, HIGH); // LED off by default

    connectWiFi();
    server.on("/command", HTTP_POST, handleCommand);
    server.begin();

}

void loop() {
    server.handleClient();
    if (digitalRead(RESET_BUTTON) == LOW){
      delay(500);
      Serial.println("Button is pressed!");
      digitalWrite(RELAY_PIN, HIGH);
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Locked!");
      lcd.setBacklight(HIGH);
      delay(2000);
      lcd.setBacklight(LOW);
      lcd.clear();

    }
}
