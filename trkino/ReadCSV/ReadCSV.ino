/**
  Test file showing how to read a CSV file from the SD card.
*/
#include <CSV_Parser.h>
#include <SPI.h>
#include <SD.h>

const uint8_t chipSelect = 4;

void setup() {
  Serial.begin(115200);
  Serial.print(F("Initializing SD card..."));
  if (!SD.begin(chipSelect)) {
    Serial.println(F("SD card initialization failed!"));
    while (1);
  }
  Serial.println(F("SD card initialization done."));

  CSV_Parser cp("uxLLLuc");

  // The line below (readSDfile) wouldn't work if SD.begin wasn't called before.
  // readSDfile can be used as conditional, it returns 'false' if the file does not exist.
  if (cp.readSDfile("/POZYXCFG.CSV")) {
    // These types have to match the size assigned in the format above, otherwise
    // it will break the data alignment.
    uint32_t *devices_ids = static_cast<uint32_t*>(cp["network_id"]);
    int32_t *devices_x = static_cast<int32_t*>(cp["x"]);
    int32_t *devices_y = static_cast<int32_t*>(cp["y"]);
    int32_t *devices_z = static_cast<int32_t*>(cp["z"]);
    uint8_t *devices_is_tag = static_cast<uint8_t*>(cp["is_tag"]);

    for(size_t i = 0; i < cp.getRowsCount(); i++) {
      Serial.print(devices_ids[i]);
      Serial.print(F(" | "));
      Serial.print(devices_x[i]);
      Serial.print(F(" | "));
      Serial.print(devices_y[i]);
      Serial.print(F(" | "));
      Serial.print(devices_z[i]);
      Serial.print(F(" | "));
      Serial.println(devices_is_tag[i]);
    }
  } else {
    Serial.println("ERROR: The file does not exist...");
  }
}

void loop() {

}
