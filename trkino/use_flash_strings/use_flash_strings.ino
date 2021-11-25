#include <avr/pgmspace.h>

char const first_msg[] PROGMEM = "Hello this is a test";
char const second_msg[] PROGMEM = "This is another one";
char const third_msg[] PROGMEM = "And this is the last";
char const * const string_table[] PROGMEM = {first_msg, second_msg, third_msg};

char buffer[32];


void setup() {
  Serial.begin(115200);
  Serial.println("OK");
}

void loop() {
  for (size_t i = 0; i < 3; ++i) {
    // strcpy_P(dest, src) copies a string from program space to SRAM.
    // pgm_read_word(address) reads a word from program space.
    strcpy_P(buffer, reinterpret_cast<char *>(pgm_read_word(&(string_table[i]))));
    Serial.println(buffer);
    delay(500);
  }
}
