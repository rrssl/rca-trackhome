/*
  Demo on how to read from and write to EEPROM memory.
 */
#include <EEPROM.h>

void setup() {
  Serial.begin(115200);
  Serial.println(EEPROM.length());
  EEPROM.update(0, 0);
  for (size_t i = 0; i < EEPROM.length(); ++i) {
    Serial.print(EEPROM.read(i));
    Serial.print(" ");
  }
  Serial.println();
}

void loop() {}
