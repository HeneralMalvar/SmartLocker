#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

const char* ssid = "leviwifi";
const char* password = "levi121423";

ESP8266WebServer server(80);

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to Wi-Fi...");
  }
  Serial.println("Connected to Wi-Fi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // Define endpoints
  server.on("/command", []() {
    String command = server.arg("command");

    if (command == "LED_ON") {
      digitalWrite(D1, HIGH);  // Assume LED is on D1
      server.send(200, "text/plain", "LED turned ON");
    } else if (command == "LED_OFF") {
      digitalWrite(D1, LOW);
      server.send(200, "text/plain", "LED turned OFF");
    } else if (command.startsWith("LCD_DISPLAY_ACCESS_GRANTED:")) {
      String name = command.substring(26);  // Extract name
      Serial.println("ACCESS GRANTED for " + name);
      // Code to display on LCD
      server.send(200, "text/plain", "Access Granted displayed on LCD");
    } else if (command == "LCD_DISPLAY_ACCESS_DENIED") {
      Serial.println("ACCESS DENIED");
      // Code to display on LCD
      server.send(200, "text/plain", "Access Denied displayed on LCD");
    } else {
      server.send(400, "text/plain", "Unknown command");
    }
  });

  server.begin();
  Serial.println("Server started");
}

void loop() {
  server.handleClient();
}
