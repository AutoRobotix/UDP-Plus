import asyncio
import socket
import uuid
import csv
import io

#TODO: rate limiter
#TODO: pending operation cleaner -> move to failed operations
#TODO: retry failed operations every n seconds
#TODO: op_id+ip pairing in pending operations and control
#TODO: come esportare messaggi/file in arrivo per accedervi dall'esterno? 
#TODO: handle pending operations concurrency
#TODO: use longer op_id

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

        #self.loop = asyncio.get_event_loop()

        # pending_operation = op_id : {'length': n, 'chunks_id': [chunk_id, ], 'chunks': [chunk, ], 'events': {'chunk_id': event}}
        self.pending_operations = {}
        self.failed_operations = {}
        self.messages = {}

    ### --- Networking --- ###

    async def udp_receiver(self):
        """ Continuously receive UDP packets and dispatch commands """
        loop = asyncio.get_running_loop()
        while True:
            data, address = await loop.sock_recvfrom(self.udp_sock, 1024)
            sender_ip, sender_port = address
            await self.message_handler(sender_ip, sender_port, data)

    async def udp_transmitter(self, ip, port, data: bytes):
        loop = asyncio.get_running_loop()
        """ Send UDP packet """
        await loop.sock_sendto(self.udp_sock, data, (ip, port))

    ### --- Message Handling --- ###

    # packet = cmd, op_id, length, chunk_id, chunk

    async def message_handler(self, ip, port, data: bytes):
        packet = self.load_packet(data)
        cmd = int(packet[0]) if packet[0] else 0
        op_id = packet[1]
        length = packet[2] if packet[2] else 1
        chunk_id = packet[3] if packet[3] else '0'
        chunk = packet[4]

        if cmd == CMD_MESSAGE:
            # message
            if length == 1:
                message = chunk
                packet_response = [1, op_id, '', chunk_id, ''] 
                await self.send_confirm(ip, port, packet_response)
                print(message) ## come esportare il messaggio senza fare return e stoppare tutto?
                if self.messages.get(ip):
                    self.messages[ip].append(message)
                else:
                    self.messages[ip] = [message]

            # long message
            else:
                if not self.pending_operations.get(op_id):
                    self.pending_operations[f'{op_id}'] = {'length': length, 'chunks_id': [chunk_id], 'chunks': [chunk], 'events': {}}    

                elif chunk_id not in self.pending_operations[f'{op_id}']['chunks_id']:
                    self.pending_operations[f'{op_id}']['chunks_id'].append(chunk_id)
                    self.pending_operations[f'{op_id}']['chunks'].append(chunk)

                packet_response = [1, op_id, '', chunk_id, '']
                await self.send_confirm(ip, port, packet_response)

                if len(self.pending_operations[f'{op_id}']['chunks_id']) == self.pending_operations[f'{op_id}']['length']:
                    message = self.recompose_message(op_id)
                    print(message) ## come esportare il messaggio senza fare return e stoppare tutto?
                    if self.messages.get(ip):
                        self.messages[ip].append(message)
                    else:
                        self.messages[ip] = [message]

                    del self.pending_operations[f'{op_id}']

        elif cmd == CMD_CONFIRM:
            if self.pending_operations.get(op_id):
                if self.pending_operations[f'{op_id}']['events'].get(chunk_id):
                    self.pending_operations[f'{op_id}']['events'][chunk_id].set()
                    del self.pending_operations[f'{op_id}']['events'][chunk_id]

    async def message_sender(self, ip, port, message):
        #message = message.encode()
        msg_size = len(message)
        op_id = uuid.uuid4().hex[:8]  # short operation ID

        if msg_size <= CHUNK_SIZE:
            packet = ['', op_id, '', '', message]
            self.pending_operations[op_id] = {'length': 1, 'chunks': [], 'chunks_id': [], 'events': {}}
            await self.send_message(ip, port, packet)
                    
        else:
            total_chunks = (msg_size // CHUNK_SIZE) + (1 if msg_size % CHUNK_SIZE else 0)
            self.pending_operations[op_id] = {'length': total_chunks, 'chunks': [], 'chunks_id': [], 'events': {}}

            multi_send_packet = [self.send_message(ip, port,  
                                                  ['', op_id, total_chunks, i, message[i * CHUNK_SIZE : (i+1) * CHUNK_SIZE]],
                                                  ) for i in range(total_chunks)]
            await asyncio.gather(*multi_send_packet)

        del self.pending_operations[op_id]

    ### --- Utilities --- ###

    async def send_message(self, ip, port, packet: list):  
        op_id = packet[1]  
        chunk_id = str(packet[3]) if packet[3] else '0'
        self.pending_operations[op_id]['events'][chunk_id] = asyncio.Event()
        packet = self.dump_packet(packet)

        for i in range(TRIES):
            await self.udp_transmitter(ip, port, packet)

            try:
                await asyncio.wait_for(self.pending_operations[op_id]['events'][chunk_id].wait(), timeout=RETRY_TIME)
                break
            except:
                if i+1 == TRIES:
                    return # Transfer refused or peer unreachable
                
    async def send_confirm(self, ip, port, packet):
        packet = self.dump_packet(packet)
        await self.udp_transmitter(ip, port, packet)

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

    ### --- I/O Loops --- ###

    async def input_loop(self, target_ip: str, target_port: int):
        """
        Read user input and send messages.
        """
        loop = asyncio.get_running_loop()
        while True:
            msg = await loop.run_in_executor(None, input, "> ")
            await self.message_sender(target_ip, target_port, msg)

    def run(self, target_ip: str, target_port: int = 25252):
        async def main():
            recv_task = asyncio.create_task(self.udp_receiver())
            input_task = asyncio.create_task(self.input_loop(target_ip, target_port))
            await asyncio.gather(recv_task, input_task)
        asyncio.run(main())

    #def stop(self):
    #    pass
    

#UDP_Plus('192.168.168.148').run('192.168.168.67', 25252)
