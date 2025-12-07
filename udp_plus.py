import asyncio
import socket
import base64
import uuid
import time
import csv
import io

#TODO: rate limiter
#TODO: pending operation cleaner -> i transfer interrotti rimangono in pending_operations
#TODO: pending+completed operation cleaner
#TODO: op_id+ip pairing in pending operations and control
#TODO: use longer op_id
#TODO: implement timestamps
#TODO: what if uuid collides?

CHUNK_SIZE = 512
TRIES = 3
RETRY_TIME = 2
RETRY_FAILURES_TIME = 600 # seconds
CLEAN_PENDING_TIME = 60

CMD_MESSAGE = 0
CMD_CONFIRM = 1

class UDP_Plus:

    def __init__(self, ip, port=25252):
        # Setup UDP socket (IPv6 for wider compatibility)
        self.udp_port = port
        self.node_ip = ip #socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)[1][4][0]

        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind((self.node_ip, self.udp_port))
        self.udp_sock.setblocking(False)

        # pending_operation = op_id : {'length': n, 'chunks_id': [chunk_id, ], 'chunks': [chunk, ], 'events': {'chunk_id': event}}
        self.pending_operations = {}
        self.completed_operations = []

        self.loop = asyncio.get_running_loop()

        self._recv_task = None
        self._send_task = None

        # recv_bucket = (sender_ip: str, message: str, timestamp: int)
        self.recv_bucket = asyncio.Queue()
    #    # send_bucket = (target_ip: str, target_port: int, message: str)
    #    self.send_bucket = asyncio.Queue()

    #    self.fail_bucket = asyncio.Queue()

    ### --- Networking --- ###

    async def udp_receiver(self):
        """ Receive UDP packets and dispatch commands """
        while True:
            data, address = await self.loop.sock_recvfrom(self.udp_sock, 1024)
            sender_ip, sender_port = address
            await self.message_handler(sender_ip, sender_port, data)

    #async def udp_transmitter(self):
    #    """ Send UDP packets from the send bucket """
    #    while True:
    #        ip, port, data = await self.send_bucket.get()
    #        await self.message_sender(ip, port, data)

    ### --- Message Handling --- ###

    # packet = cmd, op_id, length, chunk_id, chunk

    async def message_handler(self, ip, port, data: bytes):
        packet = self.load_packet(data)
        cmd = int(packet[0]) if packet[0] else 0
        op_id = packet[1]
        length = int(packet[2]) if packet[2] else 1
        chunk_id = str(packet[3]) if packet[3] else '0'
        chunk = base64.b64decode(packet[4].encode()).decode()
        timestamp = packet[5] if len(packet) > 5 else None

        if cmd == CMD_MESSAGE:
            # message
            if length == 1:
                message = chunk
                packet_response = [1, op_id, '', chunk_id, ''] 
                await self.send_confirm(ip, port, packet_response)
                await self.recv_bucket.put((ip, message, timestamp))
                #self.completed_operations.append(op_id)

            # long message
            else:
                if not self.pending_operations.get(op_id): # and op_id not in self.completed_operations:
                    self.pending_operations[f'{op_id}'] = {'length': length, 'chunks_id': [chunk_id], 'chunks': [chunk], 'events': {}, 'timestamp': timestamp}

                elif chunk_id not in self.pending_operations[f'{op_id}']['chunks_id']:
                    self.pending_operations[f'{op_id}']['chunks_id'].append(chunk_id)
                    self.pending_operations[f'{op_id}']['chunks'].append(chunk)

                packet_response = [1, op_id, '', chunk_id, '']
                await self.send_confirm(ip, port, packet_response)

                # if transfer is stopped before completion, the pending operation will remain !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                if len(self.pending_operations[f'{op_id}']['chunks_id']) == self.pending_operations[f'{op_id}']['length']:
                    message = self.recompose_message(op_id)

                    await self.recv_bucket.put((ip, message, timestamp))
                    #self.completed_operations.append(op_id)
                    del self.pending_operations[f'{op_id}']

        elif cmd == CMD_CONFIRM:
            if self.pending_operations.get(op_id):
                if self.pending_operations[f'{op_id}']['events'].get(chunk_id):
                    self.pending_operations[f'{op_id}']['events'][chunk_id].set()
                    del self.pending_operations[f'{op_id}']['events'][chunk_id]

    async def message_sender(self, ip, port, message):
        message = base64.b64encode(message.encode()).decode()
        msg_size = len(message)
        op_id = uuid.uuid4().hex[:8]  # short operation ID
        timestamp = time.time()

        if msg_size <= CHUNK_SIZE:
            packet = ['', op_id, '', '', message, timestamp] # timestamp
            self.pending_operations[op_id] = {'length': 1, 'chunks': [], 'chunks_id': [], 'events': {}, 'timestamp': timestamp}
            confirm = [await self.send_packet(ip, port, packet)]
                    
        else:
            total_chunks = (msg_size // CHUNK_SIZE) + (1 if msg_size % CHUNK_SIZE else 0)
            self.pending_operations[op_id] = {'length': total_chunks, 'chunks': [], 'chunks_id': [], 'events': {}, 'timestamp': timestamp} # 'timestamp': timestamp

            confirm = [self.send_packet(ip, port,  
                                                  ['', op_id, total_chunks, i, message[i * CHUNK_SIZE : (i+1) * CHUNK_SIZE], timestamp], # 'timestamp': timestamp
                                                  ) for i in range(total_chunks)]
            await asyncio.gather(*confirm)

        del self.pending_operations[op_id]
        return all(confirm) # True if all chunks confirmed, False otherwise

    ### --- Utilities --- ###

    async def send_packet(self, ip, port, packet: list):  
        op_id = packet[1]  
        chunk_id = str(packet[3]) if packet[3] else '0'
        self.pending_operations[op_id]['events'][chunk_id] = asyncio.Event()
        packet = self.dump_packet(packet)

        for i in range(TRIES):

            try:
                await self.loop.sock_sendto(self.udp_sock, packet, (ip, port))
                await asyncio.wait_for(self.pending_operations[op_id]['events'][chunk_id].wait(), timeout=RETRY_TIME)
                #break 
                return True
            except:
                if i+1 == TRIES: # Transfer refused or peer unreachable
                    #await self.fail_bucket.put((ip, port, packet))
                    return False
                
    async def send_confirm(self, ip, port, packet):
        packet = self.dump_packet(packet)
        try:
            await self.loop.sock_sendto(self.udp_sock, packet, (ip, port))
        except:
            pass

    def dump_packet(self, packet: list):
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(packet)
        return output.getvalue().strip().encode()
    
    def load_packet(self, packet):
        input_stream = io.StringIO(packet.decode())
        reader = csv.reader(input_stream, quoting=csv.QUOTE_MINIMAL)
        return next(reader)
    
    def recompose_message(self, op_id):
        """Concatenate text chunks (in order) and return string."""
        ordered = [self.pending_operations[op_id]['chunks'][self.pending_operations[op_id]['chunks_id'].index(str(i))] for i in range(self.pending_operations[op_id]['length'])]
        return "".join(ordered)
    
    def operation_cleaner(self):
        pass

    ### --- Start & Stop --- ###
    
    async def start(self):
        self._recv_task = asyncio.create_task(self.udp_receiver())
        #self._send_task = asyncio.create_task(self.udp_transmitter())

    def stop(self):
        self._recv_task.cancel()
        #self._send_task.cancel()
        self.udp_sock.close()

    ### --- API --- ###

    async def put_message(self, ip, port, message):
        return await self.message_sender(ip, port, message)

    async def get_message(self):
        return await self.recv_bucket.get()