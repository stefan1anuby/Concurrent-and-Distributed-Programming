import socket
import time
import csv
import asyncio
from aioquic.asyncio.client import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
import statistics_utility


OUTPUT_FILE = "/app/output/client_log.csv"  # Path inside the container

def tcp_streaming_client(server_ip, port, data_size=1024 * 1024 * 1024, buffer_size=1024):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((server_ip, port))

    print("[TCP Streaming] Connection to the server has been made")

    data = b'0' * buffer_size
    total_sent = 0
    total_messages = 0
    start_time = time.time()

    while total_sent < data_size:
        client.sendall(data)
        total_messages += 1
        total_sent += len(data)

    end_time = time.time()
    
    print(f"\n[TCP Streaming] Client Summary: Total Messages Sent: {total_messages}, Total Bytes Sent: {total_sent}, Total Transmission Time: {end_time - start_time:.2f} seconds")
    client.close()

    return total_messages,total_sent, end_time - start_time

def tcp_stop_and_wait_client(server_ip, port, data_size=500 * 1024 * 1024, buffer_size=1024):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((server_ip, port))

    data = b'0' * buffer_size
    total_sent = 0
    total_messages = 0
    start_time = time.time()

    while total_sent < data_size:
        client.sendall(data)  #Send one chunk
        total_sent += len(data)
        total_messages += 1
        #time.sleep(0.01)
        #Wait for acknowledgment before sending the next chunk
        ack = client.recv(3)
        if ack != b"ACK":
            print("[TCP Stop-and-Wait] Unexpected acknowledgment received!")

    end_time = time.time()
    print(f"\n[TCP Stop-and-Wait] Client Summary: Total Messages Sent: {total_messages}, Total Bytes Sent: {total_sent}, Total Transmission Time: {end_time - start_time:.2f} seconds")

    #time.sleep(1)
    client.close()

    return total_messages,total_sent, end_time - start_time

    
def udp_streaming_client(server_ip, port, data_size=500 * 1024 * 1024, buffer_size=1024):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print("[UDP] Connection to the server has been made")

    data = b'1' * buffer_size
    total_sent = 0
    total_messages = 0
    start_time = time.time()

    while total_sent < data_size:
        client.sendto(data, (server_ip, port))
        total_sent += len(data)
        total_messages += 1

    client.sendto(b'STOP', (server_ip, port))
    end_time = time.time()
    time.sleep(1)
    client.close()
    print(f"\n[UDP Streaming] Client Summary, Total Messages Sent: {total_messages}, Total Bytes Sent: {total_sent}, Total Transmission Time: {end_time - start_time:.2f} seconds")
    return total_messages,total_sent, end_time - start_time

def udp_stop_and_wait_client(server_ip, port, data_size=500 * 1024 * 1024, chunk_size=1024):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print("[UDP Stop-and-Wait] Connection to the server has been made")

    data = b'1' * chunk_size  # Smaller chunk size
    total_sent = 0
    total_messages = 0
    start_time = time.time()

    while total_sent < data_size:
        client.sendto(data, (server_ip, port))  # Send one chunk
        total_sent += len(data)
        total_messages += 1

        # Wait for acknowledgment before sending the next chunk
        try:
            client.settimeout(1.0)  # Timeout if no ACK is received
            ack, _ = client.recvfrom(chunk_size)
            if ack != b"ACK":
                print("[UDP Stop-and-Wait] Unexpected acknowledgment received!")
        except socket.timeout:
            print("[UDP Stop-and-Wait] No ACK received, resending last message...")
            total_sent -= len(data)  # Re-send the last chunk
            total_messages -= 1
            continue  # Retry sending the same chunk

    # Send termination message to the server
    client.sendto(b"STOP", (server_ip, port))
    print("[UDP Stop-and-Wait] Sent termination signal to server.")

    end_time = time.time()
    print(f"\n[UDP Stop-and-Wait] Client Summary, Total Messages Sent: {total_messages}, Total Bytes Sent: {total_sent}, Total Transmission Time: {end_time - start_time:.2f} seconds")

    time.sleep(1)
    client.close()

    return total_messages,total_sent, end_time - start_time

async def send_data(host, port, data_size=500 * 1024 * 1024, buffer_size=1024):
    """ Sends data to the QUIC server using a stream with proper flow control. """
    config = QuicConfiguration(is_client=True)
    config.verify_mode = False  # Allow self-signed certificates

    async with connect(host, port, configuration=config) as protocol:
        print("[QUIC Streaming] Connection to the server has been made")

        data = b'1' * buffer_size  # Use smaller chunk sizes
        total_sent = 0
        total_messages = 0
        start_time = time.time()

        stream_id = protocol._quic.get_next_available_stream_id()  # Get a new stream ID
        while total_sent < data_size:
            protocol._quic.send_stream_data(stream_id, data)  # Send data on the stream
            protocol.transmit()  # Ensure data is flushed to the network
            total_sent += len(data)
            total_messages += 1
            await asyncio.sleep(0.001)  # Prevent flooding the network


        # Explicitly close the stream after sending all data
        protocol._quic.send_stream_data(stream_id, b"", end_stream=True)
        protocol.transmit()
        total_messages += 1

        end_time = time.time()
        print(f"\n[Quic Streaming] Client Summary: Total Messages Sent: {total_messages}, Total Bytes Sent: {total_sent}, Total Transmission Time: {end_time - start_time:.2f} seconds")

        # Close connection explicitly to trigger `connection_lost()`
        await asyncio.sleep(1)  # Give time for server processing
        protocol.close()
        print("[QUIC Streaming] Connection closed.")
        
async def quic_client(host, port, data_size):
    await send_data(host, port, data_size=data_size)



if __name__ == "__main__":
    print("----------- SENDING 500 MB -----------")
    #print("----------- SENDING 1 GB -----------")
    data_size_500mb=1 * 1024 * 1024
    #results_list = []
    #for i in range(3):
    #    time.sleep(1)
    #    results = udp_stop_and_wait_client("server", 12345 + i, data_size=data_size_500mb)
    #    results_list.append(results)

    #stats = statistics_utility.collect_statistics(results_list)
    #statistics_utility.print_statistics("Client UDP Stop and Wait", "500MB", stats)
    #time.sleep(1)
    #tcp_stop_and_wait_client("server",12346, data_size=data_size_500mb)
    time.sleep(1)
    udp_streaming_client("server", 12347, data_size=data_size_500mb)
    #time.sleep(1)
    #udp_stop_and_wait_client("server",12348, data_size=data_size_500mb)
    #time.sleep(1)
    #asyncio.run(quic_client("server", 12349, data_size=data_size_500mb))
    
    #time.sleep(1)
    #asyncio.run(quic_client("server", 12349, data_size=data_size_500mb))
    
    #print("----------- SENDING 1 GB -----------")
    #data_size_1gb=1024 * 1024 * 1024
    #time.sleep(1)
    #tcp_streaming_client("server", 12345, data_size=data_size_1gb)
    #time.sleep(1)
    #tcp_stop_and_wait_client("server",12346, data_size=data_size_1gb)
    #time.sleep(1)
    #udp_streaming_client("server", 12347, data_size=data_size_1gb)
    #time.sleep(1)
    #udp_stop_and_wait_client("server",12348, data_size=data_size_1gb)
    #time.sleep(1)
    #asyncio.run(quic_client("server", 12349, data_size=data_size_1gb))