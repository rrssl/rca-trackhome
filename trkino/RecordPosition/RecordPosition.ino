/**
  Record positions using the Pozyx shield.
*/
#include <Pozyx.h>
#include <Pozyx_definitions.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>

#define DEBUG
#ifdef DEBUG
  #define DEBUG_BEGIN_SERIAL(x) Serial.begin(x)
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)
  #define DEBUG_PRINTHEX(x) Serial.print(x, HEX)
  #define DEBUG_PRINTLNHEX(x) Serial.println(x, HEX)
#else
  #define DEBUG_BEGIN_SERIAL(x)
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
  #define DEBUG_PRINTHEX(x)
  #define DEBUG_PRINTLNHEX(x)
#endif

const uint8_t chipSelect = 4;

uint16_t remote_id = 0x7625;  // set this to the ID of the remote device
bool remote = false;          // set this to true to use the remote ID

const uint8_t num_anchors = 4;                                     // number of anchors
uint16_t anchors[num_anchors] = {0x681D, 0x685C, 0x0D31, 0x0D2D};  // network id of the anchors
int32_t anchors_x[num_anchors] = {520, 3270, 4555, 400};           // anchor x-coordinates in mm
int32_t anchors_y[num_anchors] = {0, 400, 2580, 3180};             // anchor y-coordinates in mm
int32_t heights[num_anchors] = {1125, 2150, 1630, 1895};           // anchor z-coordinates in mm

uint8_t algorithm = POZYX_POS_ALG_UWB_ONLY;  // positioning algorithm to use
uint8_t dimension = POZYX_3D;                // positioning dimension
int32_t height = 1000;                       // height of device, required in 2.5D positioning

File dataFile;
// Each record is (t, x, y, z) in [ms, mm, mm, mm].
int32_t dataRow[4] = {0};
// Length of a cycle in ms. It should probably not be lower than 2000ms!
size_t cycle_length = 10000;
// dataRow is 16 bytes long, so it takes 512/16=32 cycles to actually write to
// the SD card. With 10s cycles, this means 1 write every 5min 20s.
// The parameters below allow to flush more often.
size_t flush_period = 0;  // flushes every x cycle (disabled if 0)
size_t cycles = 0;

void setup() {
  DEBUG_BEGIN_SERIAL(115200);

  // Initialize the SD card.
  DEBUG_PRINT(F("Initializing SD card... "));
  if (!SD.begin(chipSelect)) {
    DEBUG_PRINTLN(F("SD card initialization failed!"));
    while (1);
  }
  DEBUG_PRINTLN(F("SD card initialization done."));

  // Load the configuration files.
  File countFile = SD.open("SYSINIT.DAT", O_CREAT | O_RDWR);
  uint8_t fileCount = 0;
  if (countFile.available()) {
    countFile.seek(0);
    fileCount = countFile.read();
    DEBUG_PRINT(F("Contents of SYSINIT.DAT: "));
    DEBUG_PRINTLN(fileCount);
    countFile.seek(0);
  }
  countFile.write(fileCount + 1);
  countFile.close();

  // Create a new file.
  char dataFilename[12];
  sprintf(dataFilename, "REC%05hhu.DAT", fileCount);
  dataFile = SD.open(dataFilename, FILE_WRITE);
  if (dataFile) {
    DEBUG_PRINT(F("Opened "));
    DEBUG_PRINTLN(dataFilename);
  } else {
    DEBUG_PRINTLN(F("Could not open the data file!"));
    while (1);
  }

  if(Pozyx.begin() == POZYX_FAILURE){
    DEBUG_PRINTLN(F("Unable to connect to Pozyx shield!"));
    while (1);
  }
  DEBUG_PRINTLN(F("Connected to Pozyx shield"));

  DEBUG_PRINTLN(F("Performing manual anchor configuration"));
  if(!remote){
    remote_id = NULL;
  }
  // clear all previous devices in the device list
  Pozyx.clearDevices(remote_id);
  // sets the anchor manually
  setAnchorsManual();
  // sets the positioning algorithm
  Pozyx.setPositionAlgorithm(algorithm, dimension, remote_id);
  printCalibrationResult();

  delay(500);
  DEBUG_PRINTLN(F("Starting positioning:"));
}

void loop() {
  // Turn on the LED to indicate now is not the time to unplug
  analogWrite(LED_BUILTIN, HIGH);
  delay(1000);
  uint32_t time = millis();
  // Do positioning
  coordinates_t position;
  int status;
  if (remote) {
    status = Pozyx.doRemotePositioning(remote_id, &position, dimension, height, algorithm);
  } else {
    status = Pozyx.doPositioning(&position, dimension, height, algorithm);
  }
  if (status == POZYX_SUCCESS) {
    printCoordinates(position);
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
    printErrorCode("positioning");
  }
  // We're done, turn off the LED and wait.
  analogWrite(LED_BUILTIN, LOW);
  delay(cycle_length - 1000 - (millis() - time));
}

// prints the coordinates for either humans or for processing
void printCoordinates(coordinates_t coor){
  uint16_t network_id = remote_id;
  if (network_id == NULL){
    network_id = 0;
  }
  DEBUG_PRINT("POS ID 0x");
  DEBUG_PRINTHEX(network_id);
  DEBUG_PRINT(", x(mm): ");
  DEBUG_PRINT(coor.x);
  DEBUG_PRINT(", y(mm): ");
  DEBUG_PRINT(coor.y);
  DEBUG_PRINT(", z(mm): ");
  DEBUG_PRINTLN(coor.z);
}

// error printing function for debugging
void printErrorCode(String operation){
  uint8_t error_code;
  if (remote_id == NULL){
    Pozyx.getErrorCode(&error_code);
    DEBUG_PRINT("ERROR ");
    DEBUG_PRINT(operation);
    DEBUG_PRINT(", local error code: 0x");
    DEBUG_PRINTLNHEX(error_code);
    return;
  }
  int status = Pozyx.getErrorCode(&error_code, remote_id);
  if(status == POZYX_SUCCESS){
    DEBUG_PRINT("ERROR ");
    DEBUG_PRINT(operation);
    DEBUG_PRINT(" on ID 0x");
    DEBUG_PRINTHEX(remote_id);
    DEBUG_PRINT(", error code: 0x");
    DEBUG_PRINTLNHEX(error_code);
  }else{
    Pozyx.getErrorCode(&error_code);
    DEBUG_PRINT("ERROR ");
    DEBUG_PRINT(operation);
    DEBUG_PRINT(", couldn't retrieve remote error code, local error: 0x");
    DEBUG_PRINTLNHEX(error_code);
  }
}

// print out the anchor coordinates
void printCalibrationResult(){
  uint8_t list_size;
  int status;

  status = Pozyx.getDeviceListSize(&list_size, remote_id);
  DEBUG_PRINT("list size: ");
  DEBUG_PRINTLN(status*list_size);

  if(list_size == 0){
    printErrorCode("configuration");
    return;
  }

  uint16_t device_ids[list_size];
  status &= Pozyx.getDeviceIds(device_ids, list_size, remote_id);

  DEBUG_PRINTLN(F("Calibration result:"));
  DEBUG_PRINT(F("Anchors found: "));
  DEBUG_PRINTLN(list_size);

  coordinates_t anchor_coor;
  for(int i = 0; i < list_size; i++)
  {
    DEBUG_PRINT("ANCHOR,");
    DEBUG_PRINT("0x");
    DEBUG_PRINTHEX(device_ids[i]);
    DEBUG_PRINT(",");
    Pozyx.getDeviceCoordinates(device_ids[i], &anchor_coor, remote_id);
    DEBUG_PRINT(anchor_coor.x);
    DEBUG_PRINT(",");
    DEBUG_PRINT(anchor_coor.y);
    DEBUG_PRINT(",");
    DEBUG_PRINTLN(anchor_coor.z);
  }
}

// function to manually set the anchor coordinates
void setAnchorsManual(){
  for(int i = 0; i < num_anchors; i++){
    device_coordinates_t anchor;
    anchor.network_id = anchors[i];
    anchor.flag = 0x1;
    anchor.pos.x = anchors_x[i];
    anchor.pos.y = anchors_y[i];
    anchor.pos.z = heights[i];
    Pozyx.addDevice(anchor, remote_id);
  }
  if (num_anchors > 4){
    Pozyx.setSelectionOfAnchors(POZYX_ANCHOR_SEL_AUTO, num_anchors, remote_id);
  }
}
