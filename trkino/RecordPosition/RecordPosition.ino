/**
  Record positions using the Pozyx shield.
*/
#include <Pozyx.h>
#include <Pozyx_definitions.h>
#include <Wire.h>

void setup() {
  Serial.begin(115200);

  if(Pozyx.begin() == POZYX_FAILURE){
    Serial.println(F("ERROR: Unable to connect to Pozyx shield\nReset required"));
    delay(100);
    while(1);
  } else {
    Serial.println(F("Connected to Pozyx shield"));
  }
}

void loop() {
}
