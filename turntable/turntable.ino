
#include "Movement.h"
#include "Communication.h"


Movement M;
Communication C;


void setup() {
  Serial.begin(115200);
  M.initialize();
}

void loop() {
  C.check();
  M.step();
}
