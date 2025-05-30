import socket
import threading
import time

class Controller():
    def __init__(self):
        super().__init__()
        self.IP = '192.168.203.68'
        self.port = 7776
        self.sock = None
        self.connected = False
        self.last_message = None

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

        # Start the receiving thread
        if self.connected :
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            
 
    def receive_messages(self):
        while self.connected:
            try:
                # self.sock.settimeout(2)
                message = b""
                while True:
                    chunk = self.sock.recv(1)
                    if not chunk:
                        break
                    message += chunk
                    if b'\r' in message:
                        break
                decoded_message = message[2:-1].decode('utf-8', errors='ignore')
                print("<- {}".format(decoded_message))
                self.last_message = decoded_message
            except Exception as e:
                print("Receive error:", e)
                break
    
    def send_message(self, message):
        if self.connected :
            try:
                binary_prefix = b'\x00\x07'
                binary_suffix = b'\x0d'
                full_message = binary_prefix + message.encode('utf-8') + binary_suffix
                self.sock.sendall(full_message)
                print("->", message)
            except Exception as e:
                print("Send error:", e)

    def get_last_message(self):
        return self.last_message

    def query(self, message, timeout=2.0):
        self.send_message(message)
        time.sleep(0.1)
        return self.last_message

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


# if __name__ == "__main__":
#     controller = Controller()
#     controller.Connect('192.168.203.68', 7776)

#     print(controller.query("RUe1"))

#     controller.disconnect()

