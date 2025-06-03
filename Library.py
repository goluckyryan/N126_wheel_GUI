import socket
# import threading
import time
import math

class Controller():
    def __init__(self):
        super().__init__()
        self.IP = '192.168.203.68'
        self.port = 7776
        self.sock = None
        self.connected = False
        self.last_message = None
        self.isSpinning = False
        self.spinSpeed = 0.0
        self.commandMode = None
        self.maxAccel = 0.0
        self.accelRate = 0.0
        self.velocity = 0.0
        self.deaccelRate = 0.0
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

    def seekHome(self):
        if self.connected:
            print("Seeking home position...")
            if self.position > 0 :
                self.send_message('DI-100')
            elif self.position < 0 :
                self.send_message('DI100')

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
            self.spinSpeed = float(self.queryNumber('CS')) # rev/sec

            # point to point movement parameters
            self.maxAccel = float(self.queryNumber('AM')) # rev/sec/sec, 0.167 - 5461.167
            self.accelRate = float(self.queryNumber('AC')) # rev/sec/sec
            self.deaccelRate = float(self.queryNumber('DE')) # rev/sec/sec
            self.velocity = float(self.queryNumber('VE')) # rev/sec

            self.position = int(self.queryNumber('RUe1')) # encoder position

    def getPosition(self):
        if self.connected:
            # haha = self.query('RUe1')
            # self.position = int(haha) if isinstance(haha, (int)) else None 
            # return self.position
            self.position = int(self.queryNumber('RUe1'))
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

    def setSpinSpeed(self, speed):
        if self.connected:
            print(f"Setting spin speed to {speed} rev/sec...")
            self.send_message(f"CS{speed:.1f}")
            self.spinSpeed = speed    

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

    def gotoPosition(self, position):
        if self.connected:
            print(f"Moving to position {position}...")

            while True: 
                self.current_position = int(self.queryNumber('RUe1'))  # Get current position
                print(f"Current position: {self.current_position}")
                diff = position - self.current_position
                #estimate the moving time
                distance = abs(diff) / 8192 # steps to revolutions
                print(f"Distance to target: {diff:d} steps = {distance:.2f} revolutions")
                speedUpTime = self.velocity / self.accelRate
                speedDwTime = self.velocity / self.deaccelRate
                constSpeedTime = (distance - self.velocity * (speedUpTime + speedDwTime)) / self.velocity if distance > self.velocity * (speedUpTime + speedDwTime) else 0
                estimatedTime = speedUpTime + constSpeedTime + speedDwTime
                print(f"Estimated time to reach target: {estimatedTime:.2f} seconds")

                if abs(diff) < 5:
                    print("Already at the target position.")
                    break
                elif diff > 0:
                    print(f"Moving forward by {diff} steps.")
                    self.send_message(f"DI{diff}")
                else:
                    print(f"Moving backward by {-diff} steps.")
                    self.send_message(f"DI{-diff}")

                self.send_message('FL') 
                time.sleep(estimatedTime)  # Wait a bit before checking again

    def get_last_message(self):
        return self.last_message

    def queryNumber(self, message, timeout=2.0):
        self.send_message(message)
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

    def disconnect(self):
        """Gracefully disconnect from the server."""
        self.connected = False
        try:
            if self.sock:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
                print("Disconnected from server.")
        except Exception as e:
            print("Error while disconnecting:", e)
        self.sock = None


    def send_message(self, message):
        if not self.connected:
            print("Not connected to server")
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
            self.last_message = None
            return None
        
        
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

#     # controller.reset()
#     # controller.seekHome()
#     # controller.getStatus()

#     print("Current Position:", controller.getPosition())
#     controller.disconnect()

