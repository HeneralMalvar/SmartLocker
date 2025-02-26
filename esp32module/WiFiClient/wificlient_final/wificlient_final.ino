#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <LiquidCrystal_PCF8574.h>  // Correct library for PCF8574-based I2C LCD

const char* ssid = "leviwifi";
const char* password = "levi121423";
#define SDA_PIN D2
#define SCL_PIN D1


ESP8266WebServer server(80);  // Web server instance

// Define LED pin
//const int ledPin = D1;  // Change this to the actual pin connected to your LED

// Initialize LCD (I2C address: 0x27, 16 columns, 2 rows)
LiquidCrystal_PCF8574 lcd(0x27);  // Replace with your actual I2C address

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN,SCL_PIN);
  lcd.begin(16, 2);  // Initialize the LCD, specify the number of columns and rows
  lcd.setBacklight(LOW); // Turn off backlight initially

  pinMode(LED_BUILTIN, OUTPUT);  // Assume LED is connected to pin D1
  digitalWrite(LED_BUILTIN, HIGH); // LED off by default

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to Wi-Fi...");
  }
  Serial.println("Connected to Wi-Fi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // Define the route for the HTTP command
  server.on("/command", HTTP_GET, handleCommand);

  // Start the server
  server.begin();
  Serial.println("Server started");
}

void loop() {
  // Handle incoming client requests
  server.handleClient();
}

void handleCommand() {
  // Retrieve the "command" parameter from the URL
  String command = server.arg("command");

  Serial.println("Received command: " + command);

  if (command.startsWith("LCD_DISPLAY_ACCESS_GRANTED:")) {
    String name = command.substring(26);  // Extract name from the command
    Serial.println("ACCESS GRANTED for " + name);
    
    // Display the "Access Granted" message on the LCD
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Access Granted");
    lcd.setCursor(0, 1);
    lcd.print(name);  // Print the name on the second line
    
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
   
  }else {
    // Handle other unknown commands
    Serial.println("Received unknown command");
  }

  // Send a response back to the client
  server.send(200, "text/plain", "Command received: " + command);
}


