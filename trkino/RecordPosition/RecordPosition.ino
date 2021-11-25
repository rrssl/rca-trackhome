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
uint8_t const chip_select = 4;
// --- POZYX CONFIG ---
// Id of the tag performing the positioning (0 means master tag).
uint16_t remote_id = 0;
// Positioning algorithm.
uint8_t const algorithm = POZYX_POS_ALG_UWB_ONLY;
// Positioning dimensions (2/2.5/3D).
uint8_t const dimension = POZYX_3D;
// Height of device, required in 2.5D positioning.
int32_t const height = 1000;
// --- CUSTOM CONFIG --
// Positioning period in ms. It should probably not be lower than 2000ms!
size_t const pos_period = 10000;
// dataRow is 16 bytes long, so it takes 512/16=32 records to actually write to
// the SD card. With 10s cycles, this means 1 write every 5min 20s.
// The parameters below allow to flush more often.
size_t const flush_period = 0;  // flushes every x cycle (disabled if 0)

// Error messages.
char const _sdc_err[] PROGMEM = "SD card initialization failed";
char const _poz_err[] PROGMEM = "Unable to connect to the Pozyx shield";
char const _csv_err[] PROGMEM = "Unable to open the CSV file";
char const _dat_err[] PROGMEM = "Unable to open the DAT file";
char const _tag_err[] PROGMEM = "Tag %#06x has code %#3x";
char const _ret_err[] PROGMEM = "Unable to retrieve code for tag %#06x";
char const * const _errors[] PROGMEM = {
  _sdc_err, _poz_err, _csv_err, _dat_err, _tag_err, _ret_err
};
uint8_t const sdc_err = 0;
uint8_t const poz_err = 1;
uint8_t const csv_err = 2;
uint8_t const dat_err = 3;
uint8_t const tag_err = 4;
uint8_t const ret_err = 5;

// File used to store the positioning data at every loop.
File dataFile;
// Each record is (t, x, y, z) in [ms, mm, mm, mm].
int32_t dataRow[4] = {0};
// Number of positions recorded so far.
size_t cycles = 0;


void printError(uint8_t error, uint16_t tag_id = 0, uint8_t tag_error_code = 0) {
  uint8_t buffer_len = 40;  // max length of an error message
  char err_buffer[buffer_len];
  // strcpy_P(dest, src) copies a string from program space to SRAM.
  // pgm_read_word(address) reads a word from program space.
  strcpy_P(err_buffer,
           reinterpret_cast<char *>(pgm_read_word(&(_errors[error]))));
  if (error == tag_err) {
    char tmp_buffer[buffer_len];
    sprintf(tmp_buffer, err_buffer, tag_id, tag_error_code);
    strcpy(err_buffer, tmp_buffer);
  }
  if (error == ret_err) {
    char tmp_buffer[buffer_len];
    sprintf(tmp_buffer, err_buffer, tag_id);
    strcpy(err_buffer, tmp_buffer);
  }
  Serial.print(F("ERROR: "));
  Serial.println(err_buffer);
}

void printTagError(uint16_t network_id) {
  uint8_t err_code;
  int status = Pozyx.getErrorCode(&err_code, network_id);
  if (network_id != 0 && status != POZYX_SUCCESS) {
    printError(ret_err, network_id);
    Pozyx.getErrorCode(&err_code);
  }
  printError(tag_err, network_id, err_code);
}

#ifdef DEBUG
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

void printTagConfig(uint16_t tag_id) {
  uint8_t list_size;
  int status;
  status = Pozyx.getDeviceListSize(&list_size, tag_id);
  if(status != POZYX_SUCCESS){
    printTagError(tag_id);
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
#endif // DEBUG

// Subroutine of setup(). Has side effects. Will block on error.
void setupPozyxFromCSV(const char *filename) {
  // The expected data types are hex(uint32),int32,int32,int32,uint8.
  CSV_Parser cp("uxLLLuc");
  // NB: cp.readSDfile requires SD.begin to have been called beforehand.
  if (!cp.readSDfile(filename)) {
    printError(csv_err);
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
        printTagError(remote_id);
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
  if (!dataFile) {
    printError(dat_err);
    while (1);
  }
}

void setup() {
  Serial.begin(115200);

  // Initialize the SD card.
  DEBUG_PRINT(F("Initializing SD card... "));
  if (!SD.begin(chip_select)) {
    printError(sdc_err);
    while (1);
  }
  DEBUG_PRINTLN(F("SD card initialization done."));

  // Initialize and configure the Pozyx devices.
  if(Pozyx.begin() == POZYX_FAILURE){
    printError(poz_err);
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
  DEBUG_PRINT(F("Opened "));
  DEBUG_PRINTLN(dataFile.name());

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
    printTagError(remote_id);
  }
  // We're done, turn off the LED and wait.
  analogWrite(LED_BUILTIN, LOW);
  delay(pos_period - (millis() - time));
}
