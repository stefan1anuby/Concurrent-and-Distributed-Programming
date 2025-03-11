import socket
import time
import csv
import ssl
import asyncio
import statistics_utility
from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, ConnectionTerminated

OUTPUT_FILE = "/app/output/server_log.csv"  # Path inside the container

def tcp_streaming_server(host="0.0.0.0", port=12345, buffer_size=1024):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(1)

    print(f"[TCP Streaming] Server listening on {host}:{port}")
    conn, addr = server.accept()
    print(f"[TCP Streaming] Connection from {addr}")

    start_time = time.time()
    total_bytes = 0
    total_messages = 0

    while True:
        data = conn.recv(buffer_size)
        if not data:
            break
        total_bytes += len(data)
        total_messages += 1
            
    end_time = time.time()
    print(f"[TCP Streaming] Server Summary: Total Messages: {total_messages}, Total Bytes: {total_bytes}, Total Time: {end_time - start_time:.2f} seconds")
    
    conn.close()
    server.close()

    return total_messages,total_bytes, end_time - start_time


def tcp_stop_and_wait_server(host="0.0.0.0", port=12346, buffer_size=1024):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(1)

    print(f"[TCP Stop-and-Wait] Server listening on {host}:{port}")

    conn, addr = server.accept()
    print(f"[TCP Stop-and-Wait] Connection from {addr}")

    total_bytes = 0
    total_messages = 0
    start_time = time.time()

    try:
        while True:
            data = conn.recv(buffer_size)
            if not data:
                print("[TCP Stop-and-Wait] No more data. Closing connection...")
                break  # Client closed the connection

            total_bytes += len(data)
            total_messages += 1

            conn.sendall(b"ACK")  # Send acknowledgment
    except ConnectionResetError as e:
        pass

    end_time = time.time()
    print(f"[TCP Stop-and-Wait] Server Summary: Total Messages: {total_messages}, Total Bytes: {total_bytes}, Total Time: {end_time - start_time:.2f} seconds")
   
    conn.close()
    server.close()

    return total_messages,total_bytes, end_time - start_time
    
def udp_streaming_server(host="0.0.0.0", port=12347, buffer_size=1024):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((host, port))

    print(f"[UDP Streaming] Server listening on {host}:{port}")
    
    start_time = time.time()
    total_bytes = 0
    total_messages = 0

    while True:
        data, addr = server.recvfrom(buffer_size)
        if data == b'STOP':
            break
        #print(data)
        total_bytes += len(data)
        total_messages += 1

    server.close()
    end_time = time.time()
    print(f"[UDP Streaming] Server Summary: Total Messages: {total_messages}, Total Bytes: {total_bytes}, Total Time: {end_time - start_time:.2f} seconds")
    
    return total_messages,total_bytes, end_time - start_time

def udp_stop_and_wait_server(host="0.0.0.0", port=12348, buffer_size=1024):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((host, port))

    print(f"[UDP Stop-and-Wait] Server listening on {host}:{port}")
    
    total_bytes = 0
    total_messages = 0
    start_time = time.time()

    while True:
        data, addr = server.recvfrom(buffer_size)
        
        # Check for termination message
        if data == b"STOP":
            print("[UDP Stop-and-Wait] Received termination signal. Closing session...")
            break
        
        total_bytes += len(data)
        total_messages += 1

        # Send acknowledgment
        server.sendto(b"ACK", addr)

    end_time = time.time()
    print(f"[UDP Stop-and-Wait] Server Summary: Total Messages: {total_messages}, Total Bytes: {total_bytes}, Total Time: {end_time - start_time:.2f} seconds")
    
    server.close()

    return total_messages,total_bytes, end_time - start_time

SERVER_TIMEOUT = 10
active_server_instance = None
class SimpleQuicServer(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_bytes = 0
        self.total_messages = 0
        self.start_time = time.time()
        self.last_activity_time = time.time()

        global active_server_instance
        active_server_instance = self

    def quic_event_received(self, event):
        """ Handles QUIC events, including receiving data on streams. """
        if isinstance(event, StreamDataReceived):
            self.last_activity_time = time.time()

            if self.start_time is None:
                self.start_time = time.time()  # Start tracking time on first message
            
            #print(f"[QUIC] Message received on stream {event.stream_id}, {len(event.data)} bytes")
            self.total_bytes += len(event.data)
            self.total_messages += 1
            
            # Acknowledge received data
            # I could not find how to read this from the client
            self._quic.send_stream_data(event.stream_id, b"ACK")
            self.transmit()

            # If this is the final message, close stream
            if event.end_stream:
                print(f"[QUIC] Stream {event.stream_id} closed by client.")

        # Detect when the client explicitly closes the connection
        elif isinstance(event, ConnectionTerminated):
            self.connection_lost(None)

    def connection_lost(self, exc):
        """ Called when the QUIC connection is closed. """
        end_time = time.time()
        print(f"[Quic Streaming] Server Summary: Total Messages: {self.total_messages}, Total Bytes: {self.total_bytes}, Total Time: {end_time - self.start_time:.2f} seconds")
    
        super().connection_lost(exc)


async def shutdown_server(server_task):
    """ Automatically shuts down the server after timeout """
    global active_server_instance
    while True:
        await asyncio.sleep(1)
        current_time = time.time()

        # Only shut down if a server instance exists and is inactive
        if active_server_instance and current_time - active_server_instance.last_activity_time > SERVER_TIMEOUT:
            print(f"\n[QUIC] No activity for {SERVER_TIMEOUT} seconds. Shutting down server...")
            server_task.cancel()
            break

async def quic_streaming_server():
    """ Starts a QUIC server on port 12349 and shuts down after timeout. """
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain(certfile="quic_cert.pem", keyfile="quic_key.pem")
    
    host, port = "0.0.0.0", 12349
    print(f"[QUIC] Server is running on {host}:{port}")

    server_task = asyncio.create_task(serve(host, port, configuration=config, create_protocol=SimpleQuicServer))

    # Start auto-shutdown task
    shutdown_task = asyncio.create_task(shutdown_server(server_task))

    try:
        await asyncio.gather(server_task, shutdown_task)
    except asyncio.CancelledError:
        print("[QUIC] Server shutting down...")






# THIS DOES NOT HAVE A CLIENT EQUIVALENT
class QuicStopAndWaitServer(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_bytes = 0
        self.total_messages = 0
        self.start_time = None

    def quic_event_received(self, event):
        """ Handles QUIC events, including receiving data on streams. """
        if isinstance(event, StreamDataReceived):
            if self.start_time is None:
                self.start_time = time.time()

            # Detect termination signal
            if event.data == b"STOP":
                print("[QUIC Stop-and-Wait] Received termination signal. Closing session...")
                self.connection_lost(None)
                return
            
            print(f"[QUIC Stop-and-Wait] Received message {self.total_messages+1} on stream {event.stream_id}, {len(event.data)} bytes")
            self.total_bytes += len(event.data)
            self.total_messages += 1
            
            # Send acknowledgment
            self._quic.send_stream_data(event.stream_id, b"ACK")
            self.transmit()

    def connection_lost(self, exc):
        """ Called when the QUIC connection is closed. """
        end_time = time.time()
        print("\n[QUIC Stop-and-Wait] Session Summary")
        print(f"Protocol: QUIC")
        print(f"Total Messages Received: {self.total_messages}")
        print(f"Total Bytes Received: {self.total_bytes}")
        if self.start_time:
            print(f"Total Session Duration: {end_time - self.start_time:.2f} seconds")
        super().connection_lost(exc)

async def quic_server():
    """ Starts a QUIC server on port 12349. """
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain(certfile="quic_cert.pem", keyfile="quic_key.pem")
    
    host, port = "0.0.0.0", 12349
    print(f"[QUIC Stop-and-Wait] Server is running on {host}:{port}")

    await serve(host, port, configuration=config, create_protocol=QuicStopAndWaitServer)

    await asyncio.Future()  # Keeps the server running



if __name__ == "__main__":
    #my_list = []
    #for i in range(3):
    #    results = udp_stop_and_wait_server(port=12345 + i)
    #    my_list.append(results)
    # 
    #stats = statistics_utility.collect_statistics(my_list)
    #statistics_utility.print_statistics("Server UDP Stop and Wait", "500MB", stats)
    
    #tcp_stop_and_wait_server()
    udp_streaming_server()
    #udp_stop_and_wait_server()
    #asyncio.run(quic_streaming_server())
    #asyncio.run(quic_server())