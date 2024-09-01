#ifndef COMMUNICATION_H
#define COMMUNICATION_H

#include "Movement.h"


extern Movement M;


// time between sending status messages to the RPi
const unsigned long STATUS_INTERVAL = 2000000;  // 2 seconds

// timeout for receiving commands from RPi, in microseconds
const unsigned long COMMUNICATION_TIMEOUT = 1000;  // 0.001 seconds


class Communication {

public:
  Communication();
  void check();

private:
  Stream &serial = Serial;
  uint8_t status_counter = 0;

  unsigned char command = 'X';  // 'X' means no command is currently being received
  byte buffer[8];     // buffer for receiving communication
  uint8_t n_remaining = 0;  // remaining number of characters to receive for current command
  uint8_t idx = 0;  // index in buffer to which next received byte will be written
  unsigned long t_timeout;  // time last character was received (for timeout)
  unsigned long t_status;   // time last status message was sent

  void parse_command(const unsigned char &, const time_t &);
  void parse_data();

  void send_status(const time_t &);
  void send_reset();
  void send_acknowledge();
  void send_position_reached();
  void send_homing_finished();
  void send_error();
  void send_position();

  bool moving_to_position = false;

  bool is_initialized = false;
  void initialize();
};


// I never got around to putting these into a c or cpp file ...
Communication::Communication() {}

void Communication::check() {
  unsigned long t_ = micros();

  if (moving_to_position && M.position_reached){  // reached target position
    // Serial.println("_position reached");
    moving_to_position = false;
    send_position_reached();
  }

  if (is_initialized && t_ - t_status > STATUS_INTERVAL) {
    send_status(t_);
  }

  if (serial.available() == 0) {
    if (command == 'X') return;

    if (t_ - t_timeout > COMMUNICATION_TIMEOUT) {
      Serial.println("Error: communication timeout");
      send_error();
      command = 'X';
      n_remaining = 0;
    }

    return;
  }

  const unsigned char c = serial.read();
  // Serial.print("_got: "); Serial.print(c); Serial.print(" "); Serial.println(n_remaining);

  if (n_remaining == 0) {  // new command
    t_timeout = t_;
    parse_command(c, t_);

  } else {  // currently receiving data of command
    buffer[idx++] = c;
    n_remaining--;

    if (n_remaining == 0) {
      parse_data();
      idx = 0;
      command = 'X';

    } else {
      t_timeout = t_;
    }
  }
}

void Communication::parse_command(const unsigned char &c, const time_t &t) {
  if(c == 'I'){  // initialize system
    if(is_initialized){  // only initialize an uninitialized system
      Serial.println("_Error: already ininitialized");
      send_error();
      return;
    }

    initialize();
    send_status(t);

    return;

  } else {  // any other command will only be parsed if the system has been initialized
    if(!is_initialized) {
      Serial.println("_Error: not yet initialized");
      send_error();
      return;
    }
  }

  // at this point the system has been initialized and a non-'I' command has been received
  switch (c) {
    case 'R':
      // serial.println("_Reset");
      is_initialized = false;
      status_counter = 0;
      command = 'X';
      idx = 0;
      n_remaining = 0;
      send_reset();
      break;

    case 'V':
      // serial.println("Velocity");
      command = c;
      n_remaining = 4;  // 4 bytes for velocity value (float)
      break;

    case 'P':
      // serial.println("_Position");
      command = c;
      n_remaining = 8;  // 4 bytes for position value (float), 4 bytes for velocity value (float)
      break;

    case 'Y':  // stop everything, homing, moving to position
      M.stop();
      moving_to_position = false;
      M.moving_to_position = false;
      send_acknowledge();
      break;

    case 'Z':
      // serial.println("_Info");
      send_position();
      break;

    default:
      Serial.println("_Error: unknown command");
      send_error();
      break;
  }
}


void Communication::parse_data() {
  if(command == 'V'){
      float *v = (float*) &buffer[0];  // could just write 'buffer'
      // M.setTargetVelocity(*v);  // not used anymore, 'v' command should result in exactly one round of the turntable
      M.setTargetPosition(
        M.position == M.position_max ? 0.0 : M.position_max, *v);
      send_acknowledge();
      
  } else if(command == 'P'){
      position_t *p = (position_t*) &buffer[0];
      double *v = (double*) &buffer[4];
      M.setTargetPosition(*p, *v);
      moving_to_position = true;
      send_acknowledge();
  }
}

void Communication::send_status(const time_t & t) {
  serial.print('S');
  serial.write(status_counter++);
  serial.write('\n');
  t_status = t;
}

void Communication::send_reset() {
  serial.println('R');
}

void Communication::send_acknowledge() {
  serial.println('A');
}

void Communication::send_position_reached() {
  serial.println('P');
}

void Communication::send_homing_finished() {
  serial.println('H');
}

void Communication::send_error() {
  serial.println('E');
}

void Communication::send_position() {
  // Serial.print("_Pos: "); Serial.println(M.position);
  serial.write('Z');
  char *p = (char*) &M.position;
  serial.write(p, 4);
  serial.write('\n');
}

void Communication::initialize() {
  is_initialized = true;
  t_status = micros();
}

#endif /* COMMUNICATION_H */
