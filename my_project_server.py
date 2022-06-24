__author__ = "Amitai Fensterheim"

import socket
import sys
import time
import os
import struct
import select

# Initialise socket stuff
TCP_IP = "127.0.0.1"  # Only a local server
TCP_PORT = 1456  # Just a random choice
BUFFER_SIZE = 1024  # Standard size
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((TCP_IP, TCP_PORT))
server_socket.listen(5)
os.chdir('files')

class Client:
    def __init__(self, name, password):
        self.client_socket = None
        self.name = name
        self.password = password
        self.files = []

    def establish_connection(self, new_socket):
        self.client_socket = new_socket

    def remove_socket(self):
        self.client_socket = None

    def upld(self):
        # Send message once server is ready to recieve file details
        self.client_socket.send("1")
        # Recieve file name length, then file name
        file_name_size = struct.unpack("h", self.client_socket.recv(2))[0]
        file_name = self.client_socket.recv(file_name_size)
        if file_name in os.listdir(os.getcwd()) and file_name not in self.files:
            self.client_socket.send("-1")
            return
        # Send message to let client know server is ready for document content
        self.client_socket.send("1")
        # Recieve file size
        file_size = struct.unpack("i", self.client_socket.recv(4))[0]
        # Initialise and enter loop to recive file content
        start_time = time.time()
        with open(file_name, "wb") as output_file:
            self.files.append(file_name)
            # This keeps track of how many bytes we have recieved, so we know when to stop the loop
            bytes_recieved = 0
            print "\nRecieving..."
            while bytes_recieved < file_size:
                l = self.client_socket.recv(BUFFER_SIZE)
                output_file.write(l)
                bytes_recieved += BUFFER_SIZE
        print "\nRecieved file: {}".format(file_name)
        # Send upload performance details
        self.client_socket.send(struct.pack("f", time.time() - start_time))
        self.client_socket.send(struct.pack("i", file_size))

    def list_files(self):
        print "Listing files..."
        # Get list of files in directory
        listing = os.listdir(os.getcwd())
        # Send over the number of files, so the client knows what to expect (and avoid some errors)
        self.client_socket.send(struct.pack("i", len(listing)))
        total_directory_size = 0
        # Send over the file names and sizes whilst totaling the directory size
        for i in listing:
            # File name size
            self.client_socket.send(struct.pack("i", sys.getsizeof(i)))
            # File name
            self.client_socket.send(i)
            # File content size
            self.client_socket.send(struct.pack("i", os.path.getsize(i)))
            total_directory_size += os.path.getsize(i)
            # Make sure that the client and server are syncronised
            self.client_socket.recv(BUFFER_SIZE)
        # Sum of file sizes in directory
        self.client_socket.send(struct.pack("i", total_directory_size))
        # Final check
        self.client_socket.recv(BUFFER_SIZE)
        print "Successfully sent file listing"
        return

    def dwld(self):
        self.client_socket.send("1")
        file_name_length = struct.unpack("h", self.client_socket.recv(2))[0]
        print file_name_length
        file_name = self.client_socket.recv(file_name_length)
        print file_name
        if os.path.isfile(file_name):
            # Then the file exists, and send file size
            self.client_socket.send(struct.pack("i", os.path.getsize(file_name)))
        else:
            # Then the file doesn't exist, and send error code
            print "File name not valid"
            self.client_socket.send(struct.pack("i", -1))
            return
        # Wait for ok to send file
        self.client_socket.recv(BUFFER_SIZE)
        # Enter loop to send file
        start_time = time.time()
        print "Sending file..."
        content = open(file_name, "rb")
        # Again, break into chunks defined by BUFFER_SIZE
        l = content.read(BUFFER_SIZE)
        while l:
            self.client_socket.send(l)
            l = content.read(BUFFER_SIZE)
        content.close()
        # Get client go-ahead, then send download details
        self.client_socket.recv(BUFFER_SIZE)
        self.client_socket.send(struct.pack("f", time.time() - start_time))
        return

    def delf(self):
        # Send go-ahead
        self.client_socket.send("1")
        # Get file details
        file_name_length = struct.unpack("h", self.client_socket.recv(2))[0]
        file_name = self.client_socket.recv(file_name_length)
        # Check file exists and user has access
        if os.path.isfile(file_name) and file_name in self.files:
            self.client_socket.send(struct.pack("i", 1))
            # Wait for deletion conformation
            confirm_delete = self.client_socket.recv(BUFFER_SIZE)
            if confirm_delete == "Y":
                try:
                    # Delete file
                    os.remove(file_name)
                    self.client_socket.send(struct.pack("i", 1))
                except:
                    # Unable to delete file
                    print "Failed to delete {}".format(file_name)
                    self.client_socket.send(struct.pack("i", -1))
            else:
                # User abandoned deletion
                # The server probably recieved "N", but else used as a safety catch-all
                print "Delete abandoned by client!"
                return
        else:
            # Then the file doesn't exist
            self.client_socket.send(struct.pack("i", -1))

    def quit(self):
        # Send quit conformation
        self.client_socket.send("1")
        self.client_socket.close()
        self.client_socket = None


clients = {'amitai': Client('amitai', 'amipass'), 'daniel': Client('daniel', 'danipass')}


def get_list_of_open_client_sockets(clients):
    client_sockets = []
    for client in clients.values():
        if client.client_socket is not None:
            client_sockets.append(client.client_socket)
    return client_sockets


def get_client_by_socket(client_socket):
    for client in clients.values():
        if client.client_socket is client_socket:
            return client


def new_connection():
    (new_socket, address) = server_socket.accept()
    print "\nConnected to by address: {}".format(address)
    print "waiting for username: "
    name = new_socket.recv(BUFFER_SIZE)
    if not clients.has_key(name):
        new_socket.send(struct.pack("i", -1))
        print "wrong username."
        return
    new_socket.send(struct.pack("i", 1))
    print "waiting for password: "
    password = new_socket.recv(BUFFER_SIZE)
    if clients[name].password != password:
        new_socket.send(struct.pack("i", -1))
        print "wrong password."
        return
    new_socket.send(struct.pack("i", 1))
    clients[name].establish_connection(new_socket)
    print name + " established a connection."


def server_listener():
    while True:
        open_client_sockets = get_list_of_open_client_sockets(clients)
        rlist, wlist, xlist = select.select([server_socket] + open_client_sockets, open_client_sockets,
                                            [])  # returns lists of sockets that are available for read/write.
        for current_socket in rlist:
            if current_socket is server_socket:  # when server_socket is readable, it means that there is a awaiting connection.
                new_connection()
            else:  # when the current readable socket isn't the server_socket, than it is a client_socket receving a message.
                current_client = get_client_by_socket(current_socket)
                data = current_socket.recv(BUFFER_SIZE)
                if data == "":  # A blank message "" is sent when the client closed the connection.
                    print current_socket + " closed connection."
                    current_client.remove_socket()
                else:
                    print "\nRecieved instruction: {}".format(data)
                    # Check the command and respond correctly
                    if data == "UPLD":
                        current_client.upld()
                    elif data == "LIST":
                        current_client.list_files()
                    elif data == "DWLD":
                        current_client.dwld()
                    elif data == "DELF":
                        current_client.delf()
                    elif data == "QUIT":
                        current_client.quit()


if __name__ == '__main__':
    server_listener()
