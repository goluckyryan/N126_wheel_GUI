import socket
# import threading
import time
import math

STEP_PER_REVOLUTION = 8192  # Number of steps per revolution for the stepper motor

class Controller():
    def __init__(self):
        super().__init__()
        self.IP = '192.168.203.68'
        self.port = 7776
        self.sock = None
        self.connected = False
        self.last_message = None

        self.isSpinning = False
        self.jogSpeed = 0.0 # rev/sec
        self.jogAccel = 0.0 # rev/sec/sec
        self.jogDeccel = 0.0 # rev/sec/sec

        self.commandMode = None

        self.maxAccel = 0.0 # rev/sec/sec
        self.accelRate = 0.0 # rev/sec/sec
        self.velocity = 0.0     # rev/sec
        self.deaccelRate = 0.0 # rev/sec/sec
        self.moveDistance = 0 # steps

        self.position = 0  # encoder position in steps

        self.sweepMask = 0x0000     # bit mask for spokes
        self.spokeOffset = 0 # in steps
        self.spokeWidth = 0 # in steps
        self.sweepSpeed = 0 # in rpm
        self.sweepCutOff = 0 # in rpm

        self.stop_PID_control = False

        self.temperature = 0.0  # in C
        self.encoderVelocity = 0.0 # in rpm
        self.motorVelocity = 0.0    # in rpm
        self.torque = 0.0 # diff between motor and encoder position
        self.torque_ref = 0.0 # inital value of the torque

        #QX4 parameters
        self.isQX4Updated = False
        self.qx4EncoderDemandPos = 0   # R6
        self.qx4ControUpdate = 0 # 100 us/ unit, R7
        self.qx4SlewSpeed = 0 # in 0.25 rpm /unit, R8
        self.qx4ServoSlewSpeed = 0 # in 0.25 rpm /unit, R9
        self.qx4MotorDemandPos = 0  # R;
        

    def __del__(self):
        # Destructor to ensure cleanup
        print("Controller object is being destroyed. Disconnecting...")
        self.disconnect()

    def Connect(self, IP, port):
        self.IP = IP
        self.port = port

        # connect to server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(1.0) # 1 sec
        try:
            self.sock.connect((self.IP, self.port))
            self.connected = True
        except Exception as e:
            print("Connect error:", e)

        # # Start the receiving thread
        # if self.connected :
        #     receive_thread = threading.Thread(target=self.__receive_messages, daemon=True)
        #     receive_thread.start()

        # self.send_message('RE') 
        time.sleep(0.1)
        # self.seekHome()
        self.getStatus()

    def disconnect(self):
        self.connected = False
        try:
            if self.sock:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
                print("Disconnected from server.")
        except Exception as e:
            print("Error while disconnecting:", e)
        self.sock = None

    def seekHome(self):
        if self.connected:
            print("Seeking home position...")

            direction = -1* math.sin(2*math.pi * self.position / STEP_PER_REVOLUTION)
            if direction >= 0:
                self.send_message('DI100')
            else:
                self.send_message('DI-100') 

            self.send_message('SHX0H') #seek home
            
    def setEncoderPosition(self, position):
        if self.connected and self.isSpinning == False:
            print(f"Setting encoder position to {position}...")
            self.send_message(f'EP{position}')
            
    def getStatus(self):
        if self.connected:
            self.commandMode = self.queryNumber('CM', False)

            # jogging parameters
            #check self.spinSpin is number
            self.jogSpeed = float(self.queryNumber('JS',False)) # rev/sec
            self.jogAccel = float(self.queryNumber('JA',False))

            # point to point movement parameters
            self.maxAccel = float(self.queryNumber('AM',False)) # rev/sec/sec, 0.167 - 5461.167
            self.accelRate = float(self.queryNumber('AC',False)) # rev/sec/sec
            self.deaccelRate = float(self.queryNumber('DE',False)) # rev/sec/sec
            self.velocity = float(self.queryNumber('VE',False)) # rev/sec
            self.moveDistance = float(self.queryNumber('DI',False)) # steps

            self.sweepMask = int(self.queryNumber('RU11',False)) # sweep bit
            self.spokeWidth = int(self.queryNumber('RU21',False)) 
            self.spokeOffset = int(self.queryNumber('RU31',False)) 
            self.sweepSpeed = int(self.queryNumber('RU41',False)) / 4.#  rpm
            self.sweepCutOff = int(self.queryNumber('RU51',False)) / 4. #  rpm

            self.position = int(self.queryNumber('RUe1',False)) # encoder position

            self.temperature = float(self.queryNumber('RUt1',False)) / 10 # temperature in C
            self.encoderVelocity = float(self.queryNumber('RUv1',False)) / 4. #  rpm 
            self.motorVelocity = float(self.queryNumber('RUw1',False)) / 4. #  rpm 
            self.torque_ref = float(self.queryNumber('RUx1',False))
            self.torque = 0.0 # reset torque to zero

            # firmware set the minimm sweep speed to 6 rpm
            if self.sweepSpeed < 6 :
                self.sweepSpeed = 6.0
                self.setSweepSpeed(6.0)

            self.qx4EncoderDemandPos = int(self.queryNumber('RU61',False)) # R6
            self.qx4ControUpdate = int(self.queryNumber('RU71',False)) # 100 us/ unit, R7
            self.qx4SlewSpeed = int(self.queryNumber('RU81',False)) # in 0.25 rpm /unit, R8    
            self.qx4ServoSlewSpeed = int(self.queryNumber('RU91',False)) # in 0.25 rpm /unit, R9
            self.qx4MotorDemandPos = int(self.queryNumber('RU;1',False)) #
            self.isQX4Updated = True

    def setSweepMask(self, mask : int):
        if self.connected:
            self.sweepMask = mask
            self.send_message(f'RL1{mask}')
            # print(f'Sweep mask set to {mask:04X}')
    def setSpokeWidth(self, width : int):
        if self.connected:
            self.spokeWidth = width
            self.send_message(f'RL2{int(width):d}')
    def setSpokeOffset(self, width : int):
        if self.connected:
            self.spokeOffset = width
            self.send_message(f'RL3{int(width):d}')
    def setSweepSpeed(self, speed : float):
        if self.connected:
            self.sweepSpeed = speed  # in rpm
            self.send_message(f'RL4{int(speed * 4):d}')
    def setSweepCutOff(self, cutoff : float):
        if self.connected:
            self.sweepCutOff = cutoff # in rpm
            self.send_message(f'RL5{int(cutoff * 4):d}')
    def startSpinSweep(self):
        if self.connected:
            print("Starting spin sweep...")
            self.send_message('QX1')
            self.isSpinning = True
    def stopSpinSweep(self):
        if self.connected:
            print("Stopping spin sweep...")
            self.send_message('SK')
            self.isSpinning = False

    def getPosition(self, outputMsg=True):
        if self.connected:
            # haha = self.query('RUe1')
            # self.position = int(haha) if isinstance(haha, (int)) else None 
            # return self.position
            haha = self.queryNumber('RUe1', outputMsg)
            if math.isnan(haha):
                return math.nan
            else:
                self.position = int(haha)
                return self.position

    def getTemperature(self, outputMsg=True):
        if self.connected:
            self.temperaturep = self.queryNumber('RUt1', outputMsg) / 10 # temperature in C
            return self.temperature
        else:
            return math.nan

    def getEncoderVelocity(self, outputMsg=True):
        if self.connected:
            self.encoderVelocity = self.queryNumber('RUv1', outputMsg) / 4.  # in rpm
            return self.encoderVelocity
        else:
            return math.nan
        
    def getMotorVelocity(self, outputMsg=True):
        if self.connected:
            self.motorVelocity = self.queryNumber('RUw1', outputMsg) / 4. # in rpm 
            return self.motorVelocity
        else:
            return math.nan
        
    def getTorque(self, outputMsg=True):
        if self.connected:
            self.torque = self.queryNumber('RUx1', outputMsg) - self.torque_ref # diff between motor and encoder position
            return self.torque
        else:
            return math.nan

    def reset(self):
        if self.connected:
            print("Resetting controller...")
            self.send_message('RE')
            time.sleep(0.1)
            self.seekHome()
            self.isSpinning = False

    def setMaxAccel(self, accel):
        if self.connected:
            print(f"Setting max acceleration to {accel} rev/sec^2...")
            self.send_message(f"AM{accel:.3f}")
            self.maxAccel = accel
    def setAccelRate(self, accel):
        if self.connected:
            print(f"Setting acceleration rate to {accel} rev/sec^2...")
            self.send_message(f"AC{accel:.3f}")
            self.accelRate = accel
    def setDeaccelRate(self, deaccel):
        if self.connected:
            print(f"Setting deacceleration rate to {deaccel} rev/sec^2...")
            self.send_message(f"DE{deaccel:.3f}")
            self.deaccelRate = deaccel
    def setVelocity(self, velocity):
        if self.connected:
            print(f"Setting velocity to {velocity} rev/sec...")
            self.send_message(f"VE{velocity:.1f}")
            self.velocity = velocity
    def setMoveDistance(self, distance : int):
        if self.connected:
            print(f"Setting move distance to {distance} steps...")
            self.send_message(f"DI{distance:.0f}")
            self.moveDistance = distance
            # self.position = int(self.queryNumber('RUe1')) # update position after setting move distance

    def setJogSpeed(self, speed : float):
        if self.connected:
            print(f"Setting spin speed to {speed} rev/sec...")
            self.send_message(f"JS{speed:.1f}")
            self.jogSpeed = speed    
    def setJogAccel(self, accel : float):
        if self.connected:
            print(f"Setting spin speed to {accel} rev/sec^2...")
            self.send_message(f"JA{accel:.3f}")
            self.jogAccel = accel    
    def startSpin(self):
        if self.connected:
            print("Starting spin...")
            self.send_message('CJ')
            self.isSpinning = True
    def stopSpin(self):
        if self.connected:
            print("Stopping spin...")
            self.send_message('SJ')
            self.isSpinning = False

    def setQX4EncoderDemandPos(self, position):
        if self.connected:
            self.send_message(f"RL6{position}")
            self.qx4EncoderDemandPos = position

    def setQX4ControUpdate(self, update):
        if self.connected:
            self.send_message(f"RL7{update}")
            self.qx4ControUpdate = update

    def setQX4SlewSpeed(self, speed):
        if self.connected:
            self.send_message(f"RL8{speed}")
            self.qx4SlewSpeed = speed

    def setQX4ServoSlewSpeed(self, speed):
        if self.connected:
            self.send_message(f"RL9{speed}")
            self.qx4ServoSlewSpeed = speed

    def getQX4MotorDemandPos(self, position):
        if self.connected:
            self.qx4MotorDemandPos = int(self.queryNumber('RU;1',False))
            return self.qx4MotorDemandPos
        else:
            return math.nan

    def getQX4Parameters(self):
        self.qx4EncoderDemandPos = int(self.queryNumber('RU61',False)) # R6
        self.qx4ControUpdate = int(self.queryNumber('RU71',False)) # 100 us/ unit, R7
        self.qx4SlewSpeed = int(self.queryNumber('RU81',False)) # in 0.25 rpm /unit, R8    
        self.qx4ServoSlewSpeed = int(self.queryNumber('RU91',False)) # in 0.25 rpm /unit, R9
        self.qx4MotorDemandPos = int(self.queryNumber('RU;1',False)) #
        self.isQX4Updated = True

    def startQX4LockPosition(self):
        if self.connected:
            print("Starting QX4 Lock Position...")
            self.send_message('QX4')
            time.sleep(0.1)
            self.getQX4Parameters()

    def stopQX4LockPosition(self):
        if self.connected:
            print("Stopping QX4 Lock Position...")
            self.send_message('SK')

    #======= move out from Controller to GUI, because there is no position feedback here =======
    # def gotoPosition(self, position):
    #     if self.connected:
    #         print(f"Moving to position {position}...")

    #         while True: 
    #             self.current_position = int(self.queryNumber('RUe1'))  # Get current position
    #             print(f"Current position: {self.current_position}")
    #             diff = position - self.current_position
    #             #estimate the moving time
    #             distance = abs(diff) / 8192 # steps to revolutions
    #             print(f"Distance to target: {diff:d} steps = {distance:.2f} revolutions")
    #             speedUpTime = self.velocity / self.accelRate
    #             speedDwTime = self.velocity / self.deaccelRate
    #             constSpeedTime = (distance - self.velocity * (speedUpTime + speedDwTime)) / self.velocity if distance > self.velocity * (speedUpTime + speedDwTime) else 0
    #             estimatedTime = speedUpTime + constSpeedTime + speedDwTime
    #             print(f"Estimated time to reach target: {estimatedTime:.2f} seconds")

    #             if abs(diff) < 5:
    #                 print("Already at the target position.")
    #                 break
    #             elif diff > 0:
    #                 print(f"Moving forward by {diff} steps.")
    #                 self.send_message(f"DI{diff}")
    #             else:
    #                 print(f"Moving backward by {-diff} steps.")
    #                 self.send_message(f"DI{-diff}")

    #             self.send_message('FL') 
    #             time.sleep(estimatedTime)  # Wait a bit before checking again

    def ConvertModPositionToAbsolute(self, target_position):
        current_mod_position = self.position % STEP_PER_REVOLUTION
        diff = target_position - current_mod_position
        if diff > STEP_PER_REVOLUTION / 2:
            diff -= STEP_PER_REVOLUTION
        elif diff < -STEP_PER_REVOLUTION / 2:
            diff += STEP_PER_REVOLUTION
        target_position = self.position + diff
        return target_position

    def PID_pos_control(self, target_position, max_iterations=-1, tolerance=1, Kp=0.5, Ki=0.0, Kd=0.1):
        if not self.connected:
            print("Not connected to controller.")
            return

        previous_error = 0.0
        history_error = []
        history_length = 10
        iteration = 0

        stable_count = 0
        stable_required = 2  # Number of consecutive stable readings required
        max_stepper_speed = 1000  # Define a maximum speed in step

        self.stop_PID_control = False

        # convert the target_position to the nearest equivalent absolute position 
        target_position = self.ConvertModPositionToAbsolute(target_position)
        print(f"Adjusted target absolute position: {target_position}, Rev: {target_position/STEP_PER_REVOLUTION:.2f}")

        while True:
            if self.stop_PID_control:
                print("PID control stopped by user.")
                break

            if max_iterations != -1 and iteration >= max_iterations:
                print(f"Max iterations reached. Final position: {self.getPosition(outputMsg=False)}, Target position: {target_position}")
                self.stop_PID_control = True
                break

            current_position = self.getPosition(outputMsg=False)
            if math.isnan(current_position):
                print("Failed to get current position.")
                return
        

            error = target_position - current_position
            history_error.append(error)
            if len(history_error) > history_length:
                history_error.pop(0)
            integral = sum(history_error)
            derivative = error - previous_error

            # PID output
            output = Kp * error + Ki * integral + Kd * derivative

            # Limit output to max stepper speed (in step)
            output = int(round(max(-max_stepper_speed, min(max_stepper_speed, output))))

            if abs(error) <= tolerance:
                stable_count += 1
                print(f"Target position {target_position} reached within tolerance {tolerance}.")
                if stable_count >= stable_required and max_iterations > 0:
                    self.stop_PID_control = True
                    break
            else:
                stable_count = 0

            print(f"Iteration {iteration}: Current Position: {current_position}, Error: {error}, Output: {output}, Velocity: {self.velocity}")

            # Move the motor by the calculated output (rounded to nearest integer)
            self.setMoveDistance(output)
            # counld also set the velocity based on the output
            # self.setVelocity(0.1) # 0.1 rev per sec
            # self.setVelocity(min(abs(output)/STEP_PER_REVOLUTION, self.velocity)) # convert output the rev per sec
            self.send_message('FL')  # Execute the move

            self.temperature = float(self.queryNumber('RUt1',False)) / 10 # temperature in C
            self.encoderVelocity = float(self.queryNumber('RUv1',False)) # in rev/sec
            self.motorVelocity = float(self.queryNumber('RUw1',False))
            self.torque = float(self.queryNumber('RUx1',False))

            previous_error = error

            # Small delay to allow movement to start
            time.sleep(1.0)
            iteration += 1

    def get_last_message(self):
        return self.last_message

    def queryNumber(self, message, outputMsg=True, timeout=2.0):
        self.send_message(message, outputMsg)
        if self.last_message and '=' in self.last_message:
            temp = self.last_message.split('=')[1].strip()
            # Check if temp is a number
            try:
                temp = float(temp)
            except ValueError:
                return math.nan           
            return temp
        else:
            return math.nan
        
    def checkValidMessage(self, message):
        validReadMassages = [ # message that use to read or command
            'CM', 'JS', 'JA', 'AM', 'AC', 'DE', 'VE', 'DI', 
            'RUe1', 'CJ', 'SJ', 'SP', 'RE', 'CS',
            'SHX0H', 'EP', 'RE', 'RL@1', 'QX1', 'SK', 'FL', 'FP',
            'RU11', 'RUt1', 'RUv1', 'RUw1', 'RUx1', 'RU51',
            'RU21', 'RU31', 'RU41', 'RU61', 'RU71', 'RU81', 'RU91', 'RU;1', 'QX4'
        ]
        validWriteMessages = [ # message that use to write values
            'AM', 'AC', 'DE', 'VE', 'DI', 'JS', 'JA', 'EP', 'SP',
            'RL1', 'RL2', 'RL3', 'RL4', 'RL5', 'CS', 'QX1',
            'RL6', 'RL7', 'RL8', 'RL9'
        ]

        for valid_message in validReadMassages:
            if message == valid_message:
                return True
            
        for valid_message in validWriteMessages:
            if message.startswith(valid_message):
                #check the rest of the message is a number
                try:
                    value = message[len(valid_message):]
                    if value.isdigit() or (value.startswith('-') and value[1:].isdigit()) or (value.replace('.', '', 1).isdigit() and value.count('.') < 2):
                        return True
                except Exception as e:
                    return False
            
        return False


    def send_message_oneShot(self, message):
        if not self.checkValidMessage(message):
            return None

        if not self.connected:
            print("Not connected to server, attempting to connect...")
            self.Connect(self.IP, self.port)
            if not self.connected:
                print("Failed to reconnect")
                return None
        
        try:
            # Send message
            binary_prefix = b'\x00\x07'
            binary_suffix = b'\x0d'
            full_message = binary_prefix + message.encode('utf-8') + binary_suffix
            print("->", message)
            self.sock.sendall(full_message)
            
            # Receive response
            data = self.sock.recv(1024)  # Buffer size of 1024 bytes
            decoded_message = data[2:-1].decode('utf-8', errors='ignore')
            print("<-|{}|".format(decoded_message))
            self.last_message = decoded_message
            return self.last_message
                
        except Exception as e:
            print("Send/Receive error:", e)
            self.connected = False
            self.disconnect()

    def send_message(self, message, outputMsg = True):
        if not self.checkValidMessage(message):
            return "invalid message"
        # print("Sending message:", message)

        if not self.connected:
            print("Not connected to server, attempting to connect...")
            self.Connect(self.IP, self.port)
            if not self.connected:
                print("Failed to reconnect")
                return "Failed to connect"

        try:
            # Send message
            binary_prefix = b'\x00\x07'
            binary_suffix = b'\x0d'
            full_message = binary_prefix + message.encode('utf-8') + binary_suffix
            if outputMsg :
               print("->", message)
            self.sock.sendall(full_message)
            
            # Receive response
            data = self.sock.recv(1024)  # Buffer size of 1024 bytes
            decoded_message = data[2:-1].decode('utf-8', errors='ignore')
            if outputMsg :
                print("<-|{}|".format(decoded_message))
            self.last_message = decoded_message
            return self.last_message
                
        except Exception as e:
            print("Send/Receive error:", e)
            self.connected = False
            print("Attempting to reconnect and resend...")
            self.Connect(self.IP, self.port)
            
            if self.connected:
                try:
                    # Retry sending message
                    full_message = binary_prefix + message.encode('utf-8') + binary_suffix
                    print("->", message)
                    self.sock.sendall(full_message)
                    
                    # Receive response
                    data = self.sock.recv(1024)
                    decoded_message = data[2:-1].decode('utf-8', errors='ignore')
                    print("<-|{}|".format(decoded_message))
                    self.last_message = decoded_message
                    return self.last_message
                except Exception as retry_e:
                    print("Retry Send/Receive error:", retry_e)
                    self.connected = False
                    self.disconnect()
                    self.last_message = None
                    return None
            else:
                print("Reconnection failed")
                self.last_message = None
                return None
        
    def test_connection_loss(self):
        interval = 0.0
        increment = 0.5
        max_time = 30.0
        test_message = "EP"
        results = []

        print("Starting connection loss test...")

        start_time = time.time()
        while True:
            # Wait until the specified interval
            elapsed_time = time.time() - start_time
            if elapsed_time < interval:
                time.sleep(interval - elapsed_time)

            print(f"\nTesting connection for {interval:.1f} seconds")
            result = self.send_message_oneShot(test_message)
            
            if result is None:
                results.append((interval, False, "Connection lost or failed to send/receive"))
            else:
                results.append((interval, True, f"Received: {result}"))

            # Increment interval for next iteration
            interval += increment
            start_time = time.time()
            if interval > max_time:
                break

        # Print summary
        print("\nConnection Test Summary:")
        for interval, success, message in results:
            status = "Success" if success else "Failed"
            print(f"Time {interval:.1f}s: {status} - {message}")

        return results
    # def __receive_messages(self):
    #     while self.connected:
    #         try:
    #             # self.sock.settimeout(2)
    #             message = b""
    #             while True:
    #                 chunk = self.sock.recv(1)
    #                 if not chunk:
    #                     break
    #                 message += chunk
    #                 if b'\r' in message:
    #                     break
    #             decoded_message = message[2:-1].decode('utf-8', errors='ignore')
    #             print("<- {}".format(decoded_message))
    #             self.last_message = decoded_message
    #         except Exception as e:
    #             print("Receive error:", e)
    #             break
    
    # def send_message(self, message):
    #     if self.connected :
    #         try:
    #             binary_prefix = b'\x00\x07'
    #             binary_suffix = b'\x0d'
    #             full_message = binary_prefix + message.encode('utf-8') + binary_suffix
    #             self.sock.sendall(full_message)
    #             print("->", message)
    #         except Exception as e:
    #             print("Send error:", e)




# if __name__ == "__main__":
#     controller = Controller()
#     controller.Connect('192.168.203.68', 7776)

#     controller.test_connection_loss()

#     controller.disconnect()

#     # controller.reset()
#     # controller.seekHome()
#     # controller.getStatus()

#     print("Current Position:", controller.getPosition())
#     controller.disconnect()

