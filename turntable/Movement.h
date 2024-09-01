// remember: size of a pointer is 2 bytes, size of double is 4 bytes

#ifndef MOVEMENT_H
#define MOVEMENT_H


#define position_t long
#define time_t unsigned long


const byte ENABLE_PIN = 8;
const byte STEP_PIN = 2;
const byte DIR_PIN = 5;

const unsigned long micro_seconds = 1;
const unsigned long milli_seconds = 1000;
const unsigned long seconds = 1000000;

const double ZERO_RPM = 1;  // RPM threshold below which RPM are considered to be zero (otherways delays can get huge)
const unsigned long REVERSE_DELAY = 300000;  // microseconds to wait at zero velocity when velocity changes sign

const unsigned long teeth_stepper = 24;
const unsigned long teeth_turntable = 107;


class Movement {
  public:
    Movement();
    void initialize();
    void step();

    void stop();  // decelerate to a stop
    void hard_stop();  // stop immediately

    void setDirection(uint8_t);
    void flipDirection();

    void setTargetVelocity(const double&);
    void setTargetPosition(const position_t&, const double&);

    void resetPosition();
    void goHome();

    // public because we send it to the RPi on request
    position_t position = 0;         // current position of steppers (in number of steps)
    bool moving_to_position = false;  // true if we're currently moving to a target position (rather than just going at a given velocity)

    bool position_reached = false;  // could remove this, leaving it in so I don't have to change Communicator so much ...


    const double acceleration = 10;
    const double RPM_max_default = 20;
    const int motor_steps = 200;
    const int micro_steps = 16;
    const position_t position_min = 0;
    const position_t position_max = motor_steps * micro_steps * teeth_turntable / teeth_stepper ;


  private:    
    const int steps = motor_steps*micro_steps;

    uint8_t direction = HIGH;                     // spinning direction of stepper motor, HIGH represents the 'positive' direction
    double delays = 0;                            // time between steps
    double t_next = 0;                            // time of next step
    double t_previous = 0;                        // time of previous step (used in acceleration/deceleration)
    double RPM = 0;                               // current RPM
    double RPM_target = 0;                        // target RPM
    double RPM_max = 20;
    bool is_enabled = false;

    bool accelerating_to_target_position = false; // true if we're still accelerating on the way to the target position
    position_t position_target = 0;               // target position (in number of steps)
    position_t position_decelerate = 0;           // position where we start decelerating when moving towards a target position
    position_t position_halfway = 0;              // position half-way between initial and target position, last position to start decelerating

    double RPM_to_delay();
    void enable_stepper();
    void disable_stepper();
};


// I never got around to putting these into a c or cpp file ...
Movement::Movement(){}

void Movement::initialize(){
  pinMode(STEP_PIN, OUTPUT);
  digitalWrite(STEP_PIN, LOW);

  pinMode(DIR_PIN, OUTPUT);
  digitalWrite(DIR_PIN, direction);

  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, HIGH);
}

void Movement::enable_stepper(){
    if (is_enabled) return;
    digitalWrite(ENABLE_PIN, LOW);
    is_enabled = true;
}

void Movement::disable_stepper(){
    if (!is_enabled) return;
    digitalWrite(ENABLE_PIN, HIGH);
    is_enabled = false;
}

void Movement::step(){
  const time_t t = micros();

  if(t < t_next) return;
  if(RPM == 0 && RPM_target == 0){ disable_stepper(); return; }

  // prevent me from exceeding the limits with the gamepad
  const int s = (direction == HIGH ? 1 : -1);

  // stop at the min/max positions when velocity was set
  if((s == -1 && position == position_min) || (s == 1 && position == position_max)){
    hard_stop();
    disable_stepper();
    return;
  }

  // take (half-)step
  const byte val = !digitalRead(STEP_PIN);
  digitalWrite(STEP_PIN, val);  // this is slow, for better performance we could go more low level

  // update position and process 'moving_to_position'
  if(val == HIGH){  // step is taken on rising edge
    position += s;

    if(moving_to_position){

      if(accelerating_to_target_position){  // see function setTargetPosition for details

        // we're still accelerating at the half-way point; it takes as long to decelerate from the
        // current RPM to RPM_ZERO as it does to accelerate from RPM_ZERO to the current velocity
        // --> start decelerating now to reach the target position with velocity RPM_ZERO
        if(position == position_halfway){
          setTargetVelocity(0);
          accelerating_to_target_position = false;
          // we haven't changed the pre-populated position_decelerate, shouldn't really matter
          // though because if we happen to reach it on the way it will just set the velocity
          // to zero which we've already done here ...

          // Serial.print("_Reached Halfway ");

        // we've reached the maximum allowed speed, we now know how many steps it took to reach RPM_max
        // when starting from RPM_ZERO (call it 'alpha' steps); thus we update position_decelerate s.t.
        // we start decelerating at the position that's 'alpha' steps away from the target
        } else if(RPM == RPM_max){
          position_decelerate -= position;  // this variable was already prepared in setTargetPosition
          accelerating_to_target_position = false;
          // Serial.print("_Reached RPM_max "); Serial.print(": "); Serial.print(position); Serial.print(" "); Serial.println(position_decelerate);
        }

      } else {  // we either know position_decelerate or we've already started decelerating
        if(position == position_target){
          // Serial.print("_Reached Target Position");
          moving_to_position = false;
          RPM = 0;
          RPM_target = 0;

          position_reached = !moving_to_position;

          // Note, we first have to check if we've reached the target position and we only check 
          // position_decelerate afterwards; otherwise we may miss the target position if
          // position_target == position_decelerate (which can happen if we start decelerating at
          // the halfway mark)

        } else if(position == position_decelerate){
          setTargetVelocity(0);
          // Serial.print("_Started decelerating "); Serial.println(position);
        }
      }
    }
  }

  if(RPM == RPM_target){  // true when travelling at constant speed (ie not accelerating/decelerating)
    t_next += delays;
    return;
  }

  // deal with acceleration/deceleration
  const double t_passed = (t - t_previous) / seconds;
  const double RPM_change = t_passed * acceleration;

  // RPM will always be non-negative, don't need to worry about the sign here
  if(RPM < RPM_target){
    RPM = min(RPM + RPM_change, RPM_target);

    // RPM should always be at least ZERO_RPM (when accelerating),
    // otherwise delay between steps can go to inf
    RPM = max(ZERO_RPM, RPM);

  } else {
    RPM = max(RPM - RPM_change, RPM_target);
  }

  if(RPM >= ZERO_RPM){  // true if we're not close to standstill
    delays = RPM_to_delay();
    t_previous = t_next;
    t_next += delays;
    return;
  }

  // now we're close to standstill, this point can only be reached when we decelerate

  if(RPM_target == 0){  // if target is zero RPM then we've (roughly) reached it

    // due to some rounding/timing we may not have reached the target exactly when RPM == ZERO_RPM,
    // take the remaining few steps at ZERO_RPM
    if(moving_to_position){
      // Serial.print("_ZERO_RPM ");
      RPM = ZERO_RPM;
      t_previous = t_next;
      t_next += RPM_to_delay();
      return;
    }

    RPM = 0;
    disable_stepper();
    return;
  }

  // if we get to here then we've decelerated to zero because the target velocity is of opposite
  // sign of the original velocity, now pause for a moment and turn around (then accelerate towards target RPM)
  // Serial.println("_B_flip");
  flipDirection();
  RPM_target *= -1;  // target RPM was negative, now changed to positive
  RPM = 0;
  t_next += REVERSE_DELAY;
  t_previous = t_next;  // RPM_change will be at least ZERO_RPM in the next iteration (after REVERSE_DELAY is over)
}

double Movement::RPM_to_delay(){
  const double RPS = RPM / 60;  // rounds per second
  const double SPS = RPS * steps;  // steps per second
  const double delay_ = seconds / SPS;  // delay between steps (in microseconds)
  return delay_ * 0.5;  // we take half-steps everytime 'step' is called (we only toggle the pin once)
}

void Movement::stop(){
  setTargetVelocity(0);
}

void Movement::hard_stop(){
  RPM = RPM_target = 0;
}

void Movement::setDirection(uint8_t dir){
  // Todo: make sure velocity is 0
  direction = dir;
  digitalWrite(DIR_PIN, dir);
}

void Movement::flipDirection(){
  // Todo: make sure velocity is 0
  direction = !direction;
  digitalWrite(DIR_PIN, direction);
}

void Movement::setTargetVelocity(const double& v){

  if(RPM == 0 && RPM_target == 0){  // if currently standing still then t_next will be out of date
    t_next = t_previous = micros();
  } else {  // currently running, t_next should be up to date
    t_previous = t_next;
  }

  if(v == 0) {
    RPM_target = 0;
    return;
  }

  enable_stepper();

  // if v has a different sign than the current velocity then we first slow down to zero,
  // followed by reversing the direction and accelerating; this is indicated by a negative target RPM
  const int sign = ((direction == HIGH) == (v < 0)) ? -1 : 1;
  // Serial.print("_"); Serial.print(direction[idx]); Serial.print(" "); Serial.print(v); Serial.print(" "); Serial.println(sign);

  if(RPM == 0 && sign == -1){  // if we're standing still and we have to change direction then we can immediately do so
    // Serial.println("_A_flip");
    flipDirection();
    RPM_target = max(ZERO_RPM, min(RPM_max, abs(v)));

  } else {
    RPM_target = sign * max(ZERO_RPM, min(RPM_max, abs(v)));
  }
  // Serial.print("_tv: "); Serial.print(idx); Serial.print(" "); Serial.println(RPM_target[idx]);
}

void Movement::setTargetPosition(const position_t& p_target, const double& RPM_=-1){
  // This function assumes that we start in standstill! We could try to find an
  // analytical expression for the number of steps but I'm making it easier for
  // myself and just use the measured values.
  position_reached = false;

  const position_t distance = abs(p_target - position);

  if(distance == 0) {
    moving_to_position = false;
    position_reached = true;
    return;
  }
  // Serial.print("_dist:"); Serial.println(distance);

  position_target = p_target;
  moving_to_position = true;

  RPM_max = (RPM_ == -1 ? RPM_max_default : RPM_);

  // accelerate to RPM_max, when we reach RPM_max then we save the number of steps
  // it took to get there and update position_decelerate; if we haven't reached
  // RPM_max when we're half-way to the target position then we immediately start
  // decelerating to zero (RPM_zero)
  const int sign = (p_target > position ? 1 : -1);
  setTargetVelocity(sign * RPM_max);

  // if we reach RPM_max on the way (at position p_max) then the position where we start
  // decelerating will be p_target - (p_max - p0) = p0 + p_target - p_max; we prepare
  // position_decelerate with p0 + p_target now so when max RPM is reached we only need to
  // subtract the position then (= p_max)
  position_decelerate = position + p_target;
  accelerating_to_target_position = true;

  // also save half-way position for easy checking in 'step'
  position_halfway = (position + p_target) / 2;
  // Serial.print("_P_hw "); Serial.print(": "); Serial.println(position_halfway);

  // Serial.print("_Current Pos: "); Serial.println(position);
}

void Movement::resetPosition(){
  position = 0;
}

void Movement::goHome(){
  setTargetPosition(0);
}

#endif /* MOVEMENT_H */
