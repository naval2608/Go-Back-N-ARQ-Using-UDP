from socket import *
from decimal import *
import os, random, time,sys


'''''Defination list'''''''''

'''generate a random number b/w 0 and 1'''
def gen_random_number():
        while 1:
                gen_number = random.random()
                if Decimal(gen_number) != Decimal(0.0):
                        break
	return gen_number

'''generate the ack packet to send to the client, else print the packet loss'''	
def rdt_send(message,seq_counter):
	if message:	
		seq_no = str(int(message[0:32],2))
		#expected_seq = seq_counter
		#print "Expecting seq:" + str(expected_seq)	
		#if seq_no == str(expected_seq):
		send_seq_no = '{0:032b}'.format(int(seq_no))
		pad = '0' * 16
		ack_ind = '10' * 8
		return send_seq_no + pad + ack_ind
	else:
		#print "Packet loss, sequence number = " + seq_no
		return ''

'''write data recieved in the packet to the file'''
def write_file(message,filename):
	file_desc = open(filename,'a')
	msg = str(message[64:])
	iterations = len(msg)/8
	final_data = ''
	for i in range(0,iterations):
		bit_data = str(msg[i*8:(i+1)*8])
		char_data = chr(int(bit_data, 2))
		final_data = final_data + char_data
	file_desc.write(final_data)
	file_desc.close()

'''calculate the checksum return 1 if correct else -1'''
def cal_checksum(msg):
	if msg[48:64] == '01' * 8:
		total = 0
                data = [msg[i:i+16] for i in range(0,len(msg),16)]
                for y in data:
                        total += int(y,2)
                        if total >= 65535:
                                total -= 65535
                if total == 0:
			return 1
		else:
			return -1
	else:
		return -1


'''''''''Main Program'''''''''''
#print sys.argv
if(len(sys.argv) == 5):
	hostname = sys.argv[1]
	port = int(sys.argv[2])
	filename = sys.argv[3]
	probability = float(sys.argv[4])
else:
	print "Wrong set of arguments passed"
	exit(0)


if os.path.exists(filename):
	os.remove(filename)

server_socket = socket(AF_INET,SOCK_DGRAM)
server_socket.bind((hostname,port))
print "Server is ready!!"
seq_counter = 0
while 1:
	try:
		server_socket.settimeout(60.0)
		message, client_address = server_socket.recvfrom(65535)
	except timeout:
		print "Client is not sending..Exiting!!"		
		break
	random_num = gen_random_number()
	if random_num > probability:
		checksum = cal_checksum(message)
		if checksum == 1 and message[48:64] == '01' * 8:
			got_seq_no = int(message[0:32],2)
			if got_seq_no == seq_counter:
				send_msg = rdt_send(message,seq_counter)
				if send_msg:
					server_socket.sendto(send_msg, client_address)
					'''write to file'''
					write_file(message,filename)
					#print "Processing:" + str(got_seq_no)	
					seq_counter = seq_counter + 1
			elif got_seq_no > seq_counter:
				print "Packet loss, sequence number = " + str(got_seq_no)
			elif got_seq_no < seq_counter:
				send_msg = rdt_send(message,seq_counter)
				if send_msg:
					print "Ack retransmitted:" + str(got_seq_no)
					server_socket.sendto(send_msg, client_address)
		else:
			print "Packet Discarded, Checksum not matching!!!"
	else:
		got_seq_no = int(message[0:32],2)
		print "Packet loss, sequence number = " + str(got_seq_no)
server_socket.close()





















