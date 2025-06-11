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
        self.jogSpeed = 0.0
        self.jogAccel = 0.0
        self.jogDeccel = 0.0

        self.commandMode = None

        self.maxAccel = 0.0
        self.accelRate = 0.0
        self.velocity = 0.0
        self.deaccelRate = 0.0
        self.moveDistance = 0

        self.position = 0

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
            self.commandMode = self.queryNumber('CM')

            # jogging parameters
            #check self.spinSpin is number
            self.jogSpeed = float(self.queryNumber('JS')) # rev/sec
            self.jogAccel = float(self.queryNumber('JA'))

            # point to point movement parameters
            self.maxAccel = float(self.queryNumber('AM')) # rev/sec/sec, 0.167 - 5461.167
            self.accelRate = float(self.queryNumber('AC')) # rev/sec/sec
            self.deaccelRate = float(self.queryNumber('DE')) # rev/sec/sec
            self.velocity = float(self.queryNumber('VE')) # rev/sec
            self.moveDistance = float(self.queryNumber('DI')) # steps

            self.position = int(self.queryNumber('RUe1')) # encoder position

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
            self.send_message(f"AM{accel}")
            self.maxAccel = accel

    def setAccelRate(self, accel):
        if self.connected:
            print(f"Setting acceleration rate to {accel} rev/sec^2...")
            self.send_message(f"AC{accel}")
            self.accelRate = accel
    
    def setDeaccelRate(self, deaccel):
        if self.connected:
            print(f"Setting deacceleration rate to {deaccel} rev/sec^2...")
            self.send_message(f"DE{deaccel}")
            self.deaccelRate = deaccel
    
    def setVelocity(self, velocity):
        if self.connected:
            print(f"Setting velocity to {velocity} rev/sec...")
            self.send_message(f"VE{velocity}")
            self.velocity = velocity

    def setMoveDistance(self, distance : int):
        if self.connected:
            print(f"Setting move distance to {distance} steps...")
            self.send_message(f"DI{distance}")
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

    def send_message_oneShot(self, message):
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
        # print("Sending message:", message)

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

