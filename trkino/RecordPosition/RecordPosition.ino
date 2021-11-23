/**
  Record positions using the Pozyx shield.
*/
#include <Pozyx.h>
#include <Pozyx_definitions.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <CSV_Parser.h>

#define DEBUG
#ifdef DEBUG
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)
#else
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
#endif

// --- ARDUINO CONFIG ---
// Pin used by the SD card. It is 4 on the Ethernet board.
const uint8_t chipSelect = 4;
// --- POZYX CONFIG ---
// Id of the tag performing the positioning (0 means master tag).
uint16_t remote_id = 0;
// Positioning algorithm.
uint8_t algorithm = POZYX_POS_ALG_UWB_ONLY;
// Positioning dimensions (2/2.5/3D).
uint8_t dimension = POZYX_3D;
// Height of device, required in 2.5D positioning.
int32_t height = 1000;

// File used to store the positioning data at every loop.
File dataFile;
// Each record is (t, x, y, z) in [ms, mm, mm, mm].
int32_t dataRow[4] = {0};
// Positioning period in ms. It should probably not be lower than 2000ms!
size_t pos_period = 10000;
// dataRow is 16 bytes long, so it takes 512/16=32 records to actually write to
// the SD card. With 10s cycles, this means 1 write every 5min 20s.
// The parameters below allow to flush more often.
size_t flush_period = 0;  // flushes every x cycle (disabled if 0)
size_t cycles = 0;


// Subroutine of setup(). Has side effects. Will block on error.
void setupPozyxFromCSV(const char *filename) {
  // The expected data types are hex(uint32),int32,int32,int32,uint8.
  CSV_Parser cp("uxLLLuc");
  // NB: cp.readSDfile requires SD.begin to have been called beforehand.
  if (!cp.readSDfile(filename)) {
    DEBUG_PRINTLN(F("ERROR: CSV file not found."));
    while (1);
  }
  // These types have to match the size assigned in the format string above,
  // otherwise it will break the data alignment. Conversions can be done per
  // element later.
  uint32_t *devices_id = static_cast<uint32_t*>(cp["network_id"]);
  int32_t *devices_x = static_cast<int32_t*>(cp["x"]);
  int32_t *devices_y = static_cast<int32_t*>(cp["y"]);
  int32_t *devices_z = static_cast<int32_t*>(cp["z"]);
  uint8_t *devices_is_tag = static_cast<uint8_t*>(cp["is_tag"]);

  // First iterate over all tags.
  for(size_t i = 0; i < cp.getRowsCount(); ++i) {
    if (devices_is_tag[i]) {
      // Currently, the global remote_id is that of the tag defined last in
      // the CSV. This will change when we add multi-tag support.
      remote_id = devices_id[i];
    }
  }
  // Then iterate over all anchors.
  size_t num_anchors = 0;
  for(size_t i = 0; i < cp.getRowsCount(); ++i) {
    if (!devices_is_tag[i]) {
      device_coordinates_t anchor;
      anchor.network_id = static_cast<uint16_t>(devices_id[i]);
      anchor.flag = 0x1;
      anchor.pos.x = devices_x[i];
      anchor.pos.y = devices_y[i];
      anchor.pos.z = devices_z[i];
      int status = Pozyx.addDevice(anchor, remote_id);
      if (status == POZYX_SUCCESS) {
        ++num_anchors;
      } else {
        printErrorCode(remote_id);
        while (1);
      }
    }
  }
  if (num_anchors > 4){
    Pozyx.setSelectionOfAnchors(POZYX_ANCHOR_SEL_AUTO, num_anchors,
                                remote_id);
  }
}

// Subroutine of setup(). Has side effects. Will block on error.
void setupRecordFromConfig(const char *filename) {
  // Define the data file name.
  File configFile = SD.open(filename, O_CREAT | O_RDWR);
  uint8_t fileCount;
  if (configFile.available()) { // 'available' means that there is data to read
    fileCount = configFile.peek(); // reads exactly one byte
  } else {
    fileCount = 0;
  }
  configFile.write(fileCount + 1);
  configFile.close();
  char dataFilename[12];
  sprintf(dataFilename, "REC%05hhu.DAT", fileCount);
  // Create a new data file.
  dataFile = SD.open(dataFilename, FILE_WRITE);
  if (dataFile) {
    DEBUG_PRINT(F("Opened "));
    DEBUG_PRINTLN(dataFilename);
  } else {
    DEBUG_PRINTLN(F("ERROR: Could not open the data file."));
    while (1);
  }
}

void setup() {
  Serial.begin(115200);

  // Initialize the SD card.
  DEBUG_PRINT(F("Initializing SD card... "));
  if (!SD.begin(chipSelect)) {
    DEBUG_PRINTLN(F("SD card initialization failed!"));
    while (1);
  }
  DEBUG_PRINTLN(F("SD card initialization done."));

  // Initialize and configure the Pozyx devices.
  if(Pozyx.begin() == POZYX_FAILURE){
    DEBUG_PRINTLN(F("Unable to connect to Pozyx shield!"));
    while (1);
  }
  DEBUG_PRINTLN(F("Connected to Pozyx shield"));
  DEBUG_PRINTLN(F("Configuring Pozyx..."));
  // Clear all previous devices in the device list.
  Pozyx.clearDevices(remote_id);
  // Set the devices from a CSV file on the SD card.
  setupPozyxFromCSV("/POZ_CONF.CSV");
#ifdef DEBUG
  printTagConfig(remote_id);
#endif
  // Set the positioning algorithm.
  Pozyx.setPositionAlgorithm(algorithm, dimension, remote_id);

  // Open the data file.
  setupRecordFromConfig("/REC_CONF.DAT");

  delay(500);
  DEBUG_PRINTLN(F("Starting positioning:"));
}

void loop() {
  uint32_t time = millis();
  // Turn on the LED to indicate that now is not the time to unplug
  analogWrite(LED_BUILTIN, HIGH);
  delay(1000);
  // Do positioning
  coordinates_t position;
  int status;
  if (remote_id) {
    status = Pozyx.doRemotePositioning(remote_id, &position,
                                       dimension, height, algorithm);
  } else {
    // A 0-valued remote id means that positioning is done by the master tag.
    status = Pozyx.doPositioning(&position, dimension, height, algorithm);
  }
  if (status == POZYX_SUCCESS) {
#ifdef DEBUG
    printCoordinates(position, remote_id);
#endif
    // Write the data.
    dataRow[0] = static_cast<int32_t>(time);
    dataRow[1] = position.x;
    dataRow[2] = position.y;
    dataRow[3] = position.z;
    dataFile.write(reinterpret_cast<uint8_t*>(dataRow), sizeof(dataRow));
    // Force flush periodically.
    cycles += 1;
    if (cycles == flush_period) {
      dataFile.flush();
      cycles = 0;
    }
  } else {
    // prints out the error code
    printErrorCode(remote_id);
  }
  // We're done, turn off the LED and wait.
  analogWrite(LED_BUILTIN, LOW);
  delay(pos_period - (millis() - time));
}

// prints the coordinates for either humans or for processing
void printCoordinates(coordinates_t coor, uint16_t network_id){
  Serial.print("0x");
  Serial.print(network_id, HEX);
  Serial.print(", x(mm): ");
  Serial.print(coor.x);
  Serial.print(", y(mm): ");
  Serial.print(coor.y);
  Serial.print(", z(mm): ");
  Serial.println(coor.z);
}

void printErrorCode(uint16_t network_id) {
  uint8_t error_code;
  if (network_id == 0){
    Pozyx.getErrorCode(&error_code);
    Serial.print(F("ERROR on master tag: 0x"));
    Serial.println(error_code, HEX);
    return;
  }
  int status = Pozyx.getErrorCode(&error_code, network_id);
  if (status == POZYX_SUCCESS) {
    Serial.print(F("ERROR on tag 0x"));
    Serial.print(network_id, HEX);
    Serial.print(F(": 0x"));
    Serial.println(error_code, HEX);
  } else {
    Pozyx.getErrorCode(&error_code);
    Serial.print(F("ERROR on tag 0x"));
    Serial.print(network_id, HEX);
    Serial.print(F("; but couldn't retrieve remote error. ERROR on master tag: 0x"));
    Serial.println(error_code, HEX);
  }
}

void printTagConfig(uint16_t tag_id) {
  uint8_t list_size;
  int status;
  status = Pozyx.getDeviceListSize(&list_size, tag_id);
  if(status == POZYX_FAILURE){
    printErrorCode(tag_id);
    return;
  }
  uint16_t devices_id[list_size];
  status &= Pozyx.getDeviceIds(devices_id, list_size, tag_id);

  Serial.print(F("Anchors configured: "));
  Serial.println(list_size);

  coordinates_t anchor_coords;
  for(int i = 0; i < list_size; ++i)
  {
    Pozyx.getDeviceCoordinates(devices_id[i], &anchor_coords, tag_id);
    printCoordinates(anchor_coords, devices_id[i]);
  }
}
