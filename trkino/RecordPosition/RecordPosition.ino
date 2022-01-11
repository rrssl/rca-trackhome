/**
  Record positions using the Pozyx shield.

  ////////////////////////////////////////////////////////////////
  EEPROM LAYOUT             Total size: 1024B             [-] = 1B

   Session id, 1B (0 <= x < 255)
   ^  Address of the last setup error, 1B (4 <= x < 32)
   |  ^ Address of the last loop error, 2B (32 <= x < 512)
   | _| ^
   || __| Setup errors (blocking)        Loop errors
   |||   ___________/\___________  ___________/\___________
   |||  /                        \/                        \
  [----][----][----]..[----][----][----][----]..[----][----][----]..
  0     4      |||___             32                        512
               ||_   |
               |  |  v
               |  v  Tag id (if applicable), 2B
               v  Error code, 1B
               Session id, 1B

  ////////////////////////////////////////////////////////////////

*/
#include <EEPROM.h>
#include <SPI.h>
#include <SD.h>
#include <CSV_Parser.h>
#include <Pozyx.h>
#include <Pozyx_definitions.h>
#include <Wire.h>

#define DEBUG
#ifdef DEBUG
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)

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
    uint8_t list_size = 0;
    int status = Pozyx.getDeviceListSize(&list_size, tag_id);
    if (status != POZYX_SUCCESS || list_size == 0) {
      Serial.println(F("System Error: Could not retrieve device list"));
      return;
    }
    uint16_t devices_id[list_size];
    Pozyx.getDeviceIds(devices_id, list_size, tag_id);

    Serial.print(F("Anchors configured: "));
    Serial.println(list_size);

    coordinates_t anchor_coords;
    for(uint8_t i = 0; i < list_size; ++i)
    {
      Pozyx.getDeviceCoordinates(devices_id[i], &anchor_coords, tag_id);
      printCoordinates(anchor_coords, devices_id[i]);
    }
  }

#else
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
#endif // DEBUG


// --- ERROR MANAGEMENT ---
// Error messages.
char const _sdc_err_str[] PROGMEM = "SD card initialization failed";
char const _poz_err_str[] PROGMEM = "Unable to connect to the Pozyx shield";
char const _csv_err_str[] PROGMEM = "Unable to open the CSV file";
char const _dat_err_str[] PROGMEM = "Unable to open the DAT file";
char const _tag_err_str[] PROGMEM = "Tag %#6x encountered an error";
char const _ret_err_str[] PROGMEM = "Tag %#6x is unreachable";
char const * const _err_str_arr[] PROGMEM = {
  _sdc_err_str,
  _poz_err_str,
  _csv_err_str,
  _dat_err_str,
  _tag_err_str,
  _ret_err_str,
};
uint8_t const sdc_err_t = 0;
uint8_t const poz_err_t = 1;
uint8_t const csv_err_t = 2;
uint8_t const dat_err_t = 3;
uint8_t const tag_err_t = 4;
uint8_t const ret_err_t = 5;
uint8_t const max_err_str_len = 40;  // max length of an error message

void printError(uint8_t err_t, uint8_t session_id = 255, uint16_t tag_id = 0,
                bool use_pozyx_error = false) {
  if (session_id < 255) {
    char session_str[6];
    sprintf(session_str, "[%03hhu] ", session_id);
    Serial.print(session_str);
  }
  if (err_t == tag_err_t && use_pozyx_error) {
    Serial.print(F("Pozyx "));
    Serial.println(Pozyx.getSystemError(tag_id));
    return;
  }
  char err_buffer[max_err_str_len];
  // strcpy_P(dest, src) copies a string from program space to SRAM.
  // pgm_read_word(address) reads a word from program space.
  strcpy_P(err_buffer,
           reinterpret_cast<char *>(pgm_read_word(&(_err_str_arr[err_t]))));
  if (err_t == tag_err_t || err_t == ret_err_t) {
    char tmp_buffer[max_err_str_len];
    sprintf(tmp_buffer, err_buffer, tag_id);
    strcpy(err_buffer, tmp_buffer);
  }
  Serial.print(F("System Error: "));
  Serial.println(err_buffer);
}

struct ErrorLogRecord {
  uint8_t session_id;
  uint8_t err_t;
  uint16_t tag_id;
};

class ErrorLogRing {
  public:
    ErrorLogRing() {}

    ErrorLogRing(uint8_t session_id, uint16_t mem_loc, uint8_t log_size)
      : session_id_(session_id),
        mem_beg_(mem_loc),
        mem_end_(mem_beg_ + log_size*mem_rec_size_) {
      // Find the oldest (or first empty) record in the ring, aka the 'head'.
      mem_head_ = mem_beg_;
      uint8_t head_val = EEPROM.read(mem_head_);
      if (head_val != mem_null_val_) {  // i.e. the entire ring is not empty
        uint8_t past_head_val;
        do {
          mem_head_ += mem_rec_size_;  // move head forward
          if (mem_head_ == mem_end_) {
            mem_head_ = mem_beg_;  // cycle back
            // Currently, if a single session fills the ring, there is no way
            // to know which record is the oldest one. In that case, all the
            // head values would be equal, so a break is needed here to avoid
            // an infinite loop.
            break;
          }
          past_head_val = head_val;
          head_val = EEPROM.read(mem_head_);
        // The first byte of each record should be increasing until it either
        // reaches mem_null_val_ (empty record) or it drops (oldest record).
        } while (head_val != mem_null_val_ && head_val >= past_head_val);
      }
    }

    // uint16_t getLast() const {
    //   if (EEPROM.read(mem_beg_) == mem_null_val_) return 0;  // empty ring
    //   uint16_t last_head = mem_head_ == mem_beg_ ? mem_end_ : mem_head_;
    //   last_head -= mem_rec_size_;
    //   return last_head;
    // }

    uint8_t getSessionId() const {
      return session_id_;
    }

    void log(uint8_t err_t, uint16_t tag_id = 0, bool verbose = true) {
      ErrorLogRecord rec = {session_id_, err_t, tag_id};
      EEPROM.put(mem_head_, rec);
      mem_head_ += mem_rec_size_;  // move head forward
      if (mem_head_ == mem_end_) mem_head_ = mem_beg_;  // cycle back
      if (verbose) printError(rec.err_t, rec.session_id, rec.tag_id);
    }

    void replay() const {
      if (EEPROM.read(mem_beg_) == mem_null_val_) return;  // empty ring
      uint16_t print_head = mem_head_;
      ErrorLogRecord rec;
      do {
        EEPROM.get(print_head, rec);
        if (rec.session_id != mem_null_val_) {
          printError(rec.err_t, rec.session_id, rec.tag_id);
        }
        print_head += mem_rec_size_;  // move head forward
        if (print_head == mem_end_) print_head = mem_beg_;  // cycle back
      } while (print_head != mem_head_);
    }

  private:
    static uint8_t const mem_rec_size_ = 4;
    static uint8_t const mem_null_val_ = 255;
    uint16_t mem_beg_;
    uint16_t mem_end_;
    uint16_t mem_head_;
    uint8_t session_id_;
};

void logTagError(ErrorLogRing & err_log, uint16_t tag_id = 0) {
  uint8_t err_code;
  int status = Pozyx.getErrorCode(&err_code, tag_id);
  if (tag_id != 0 && status != POZYX_SUCCESS) {
    // Log a retrieval error.
    err_log.log(ret_err_t, tag_id);
    tag_id = 0;  // this is so that printError queries the master tag
  } else {
    // Log a tag error.
    err_log.log(tag_err_t, tag_id);
  }
  printError(tag_err_t, err_log.getSessionId(), tag_id, /* use_pozyx_error */ true);
}


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
// Supremum for the setup and loop error addresses.
uint8_t const sup_setup_err_id = 32;
uint16_t const sup_loop_err_id = 512;
// Positioning period in ms. It should probably not be lower than 2000ms!
size_t const pos_period = 10000;
// dataRow is 16 bytes long, so it takes 512/16=32 records to write a full block
// to the SD card. With 10s cycles, this means 1 write every 5min 20s.
// It can be flushed more often, but the card will be worn out more quickly.
size_t const flush_period = 32;  // flushes every x cycle (disabled if 0)

// --- GLOBAL VARIABLES ---
// File used to store the positioning data at every loop.
File dataFile;
// Logs used to store setup and loop errors in EEPROM.
ErrorLogRing setup_log;
ErrorLogRing loop_log;
// Each record is (t, x, y, z) in [ms, mm, mm, mm].
int32_t dataRow[4] = {0};
// Number of positions recorded so far.
size_t cycles = 0;


// Subroutine of setup(). Has side effects. Will block on error.
void setupPozyxFromCSV(const char *filename) {
  // The expected data types are hex(uint32),int32,int32,int32,uint8.
  CSV_Parser cp("uxLLLuc");
  // NB: cp.readSDfile requires SD.begin to have been called beforehand.
  if (!cp.readSDfile(filename)) {
    setup_log.log(csv_err_t);
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
        logTagError(setup_log, remote_id);
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
void setupDataRecord(uint8_t session_id) {
  // Define the data file name.
  char dataFilename[12];  // SD lib expects 8.3 filenames
  sprintf(dataFilename, "REC%05hhu.DAT", session_id);  // hhu = uint_8
  // Create a new data file.
  dataFile = SD.open(dataFilename, FILE_WRITE);
  if (!dataFile) {
    setup_log.log(dat_err_t);
    while (1);
  }
}

void setup() {
  Serial.begin(115200);

  // Define the session id.
  uint8_t session_id = (EEPROM.read(0) + 1) % 255;
  EEPROM.write(0, session_id);
  DEBUG_PRINT(F("Session "));
  DEBUG_PRINTLN(session_id);

  // Initialize the error logs.
  setup_log = ErrorLogRing(session_id, /* mem_loc */ 4, /* log_size */ 7);
  loop_log = ErrorLogRing(session_id, /* mem_loc */ 32, /* log_size */ 120);
  Serial.println(F("--- SETUP ERROR LOG ---"));
  setup_log.replay();
  Serial.println(F("--- LOOP ERROR LOG ---"));
  loop_log.replay();

  // Initialize the SD card.
  DEBUG_PRINT(F("Initializing SD card... "));
  if (!SD.begin(chip_select)) {
    setup_log.log(sdc_err_t);
    while (1);
  }
  DEBUG_PRINTLN(F("SD card initialization done."));

  // Initialize and configure the Pozyx devices.
  if(Pozyx.begin() == POZYX_FAILURE){
    setup_log.log(poz_err_t);
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
  setupDataRecord(session_id);
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
    logTagError(loop_log, remote_id);
  }
  // We're done, turn off the LED and wait.
  analogWrite(LED_BUILTIN, LOW);
  delay(pos_period - (millis() - time));
}
