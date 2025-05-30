import socket
import threading
import time
#import keyboard

# Define the server address and port
#SERVER_ADDRESS = '192.168.0.40'  # Change this to the target system's IP
SERVER_ADDRESS = '192.168.203.68'  # Change this to the target system's IP 
# SERVER_ADDRESS = '192.168.203.69'  # Change this to the target system's IP address
SERVER_PORT = 7775

def receive_messages(sock):
    """Function to receive messages from the server."""
    while True:
        try:
            sock.settimeout(2)
            message = b""
            while True:
                chunk = sock.recv(1)
                if not chunk:
                    # Connection closed by peer
                    break
                message += chunk
                if b'\r' in message:
                    break
            # Decode the message while ignoring the binary prefix and suffix
            decoded_message = message[2:-1].decode('utf-8', errors='ignore')
            print("<- {}".format(decoded_message))
        except Exception as e:
            break

def send_messages(message, sock, server_address):
    """Function to send messages to the server."""
    while True:
        if message.lower() == 'exit':
            print("Exiting...")
            break
        try:
            # Prepend the binary bytes 0x00 and 0x07, and append 0x0D to the message
            binary_prefix = b'\x00\x07'
            binary_suffix = b'\x0d'
            full_message = binary_prefix + message.encode('utf-8') + binary_suffix
            sock.sendto(bytes(full_message), server_address)
            #hex_array = [x.encode("hex") for x in full_message]
            #print("Sent message: {}".format(hex_array))
            break
        except Exception as e:
            print("Error sending message: {}".format(e))
            break

def receive_mon_messages(sock):
    """Function to receive messages from the server."""
    print ("<- ", end=""),
    while True:
        try:
            sock.settimeout(0.050)
            message = b""
            while True:
                chunk = sock.recv(1)
                if not chunk:
                    # Connection closed by peer
                    break
                if chunk == "?":
                    sock.recv(2)
                    break
                message += chunk
                if chunk == b'\r':
                    break
            if chunk == "?":
                continue
            # Decode the message while ignoring the binary prefix and suffix
            decoded_message = message[2:-1].decode('utf-8', errors='ignore')
            print (f"{format(decoded_message):9}, ", end="") 
        except Exception as e:
            print("\r")
            break

def send_mon_messages(sock, server_address):
    """Function to send messages to the server."""
    msg_list = list()
    msg_list.append('RUt1')
    msg_list.append('RUv1')
    msg_list.append('RUw1')
    msg_list.append('RUx1')
    msg_list.append('RUe1')
    for msg in msg_list:
        try:
            # Prepend the binary bytes 0x00 and 0x07, and append 0x0D to the message
            binary_prefix = b'\x00\x07'
            binary_suffix = b'\x0d'
            full_message = binary_prefix + msg.encode('utf-8') + binary_suffix
            sock.sendto(full_message, server_address)
            time.sleep(0.010)
        except Exception as e:
            break

global KeyPressed #the almighty global variable that monitors whether the keyboard was pressed or not.

def input_thread():
    global KeyPressed
    input()             # use input() in Python3
    KeyPressed = True
    return 

#def handle_key(event):
#    global KeyPressed
#    KeyPressed = True
#    #print("KeyPressed is now:", event.name) #in case you want to know what did you pressed.
#    return 

def main():
    print("V0.1\r")
    global KeyPressed
    #keyboard.hook(lambda event: handle_key(event))
    while True:
        #message = input("")
        message = input("")
        time.sleep(0.250)
        KeyPressed = False 
        
        if message.lower() == 'mon':
	    # Start the keypress monitor
            key_press_thread = threading.Thread(target=input_thread)
            key_press_thread.daemon = True
            key_press_thread.start()
            while True:

                if KeyPressed:
                    break
                # Create a UDP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
                # Connect to the server
                sock.connect((SERVER_ADDRESS, 7776))
               
                # Start the receiving thread
                mon_receive_thread = threading.Thread(target=receive_mon_messages, args=(sock,))
                mon_receive_thread.daemon = True
                mon_receive_thread.start()
                
                # Start the sending thread
                mon_send_thread = threading.Thread(target=send_mon_messages, args=(sock, (SERVER_ADDRESS, SERVER_PORT)))
                mon_send_thread.start()
                
                # Wait for the send thread to finish
                mon_receive_thread.join()
                
                # Close the socket
                sock.close()
        else:
            # Create a UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Connect to the server
            sock.connect((SERVER_ADDRESS, 7776))
           
            # Start the receiving thread
            receive_thread = threading.Thread(target=receive_messages, args=(sock,))
            receive_thread.daemon = True
            receive_thread.start()
            
            # Start the sending thread
            send_thread = threading.Thread(target=send_messages, args=(message, sock, (SERVER_ADDRESS, SERVER_PORT)))
            send_thread.start()
            
            # Wait for the send thread to finish
            receive_thread.join()
            
            # Close the socket
            sock.close()

if __name__ == "__main__":
    main()