from socket import *
import os,sys
import re,time,fcntl
import psutil

'''''''''''Defination List'''''''''''''''

'''lock the file'''
def lock_file(file_desc):
	fcntl.flock(file_desc.fileno(),fcntl.LOCK_EX)

'''generate the message to send to the server'''
def rdt_send(file_name,mss,seq_no):
	segment_data = ''
	with open(file_name, "rb") as file_desc:		
		position = seq_no * mss
        	file_desc.seek(position,0)
        	for i in range(1,mss+1):
			byte_data = file_desc.read(1)
            		if byte_data:
				segment_data = segment_data + str(byte_data)
	file_desc.close()        
	segment = design_segment(seq_no,segment_data)
	checked_data = gen_checksum(segment)       
	return checked_data

'''generate the checksum for the message'''
def gen_checksum(msg):
        if msg:
		total = 0	
                data = [msg[i:i+16] for i in range(0,len(msg),16)]
                for y in data:
			total += int(y,2)
			if total >= 65535:
				total -= 65535
		checksum = 65535 - total
		check_sum_bits = '{0:016b}'.format(checksum)
		send_msg = msg[0:32] + check_sum_bits + msg[48:]
		return send_msg
	else:
		return '0'

'''design the packet that needs to be send, making checksum hardcoded to set of 0's bits'''
def design_segment(seq_no,segment_data):
	seq_no_bits = '{0:032b}'.format(seq_no)
    	checksum = '0' * 16
    	indicator_bits = '01' * 8
    	data = ''
    	for i in range(1,len(segment_data)+1):
        	data_character = segment_data[i-1]
        	data_byte = '{0:08b}'.format(ord(data_character))
        	data = data + data_byte
    	segment = seq_no_bits + checksum + indicator_bits + data
    	return segment

'''get the sequence no which is available to send to the server'''
def get_seq_no(window_size,seq_file):
	seq_no = -1
	file_desc = open(seq_file, "r")
	lock_file(file_desc)
	active_count = 0
	for line in reversed(file_desc.readlines()):
		if re.findall('(\d+),A\n',line):
			active_count += 1
		elif re.findall('(\d+),\n',line):
			seq_no = str(re.findall('(\d+),\n',line)[0])	
	file_desc.close()
	if active_count == window_size:
		return 	-1
	elif active_count < window_size:
		return seq_no
	else:
		print "Something is wrong"		
		return -1


'''mark the sent sequence no as active A'''
def mark_seqno_active(seq_no,seq_file):
	file_desc = open(seq_file, "r+w")
	lock_file(file_desc)
	data = file_desc.readlines()
	if data[int(seq_no)] == seq_no + ",\n":
		data[int(seq_no)] = seq_no + ",A\n"
	new_data = ''.join(data)
	file_desc.seek(0)
	file_desc.truncate()
	file_desc.write(new_data)
	file_desc.close()


'''create process which will recv from server'''
def recv_process(soc,seq_file):
	new_proc = os.fork()
	if new_proc == 0:
		#p = psutil.Process(os.getpid())
		#print 'priority-receive' + str(p.nice)
		print "process:" + str(os.getpid()) + " created to recv from server"
	       	while 1:
                	message, server_addr = soc.recvfrom(max_buff)
	                seq_no = validate_recv_msg(message)
			if seq_no != -1:
				mark_seqno_ack(seq_no,seq_file)


'''mark the seq no for which ack was recieved with D if all the above 
sequences are also marked as D'''
def mark_seqno_ack(seq_no,seq_file):
	make_change = -1
	line_counter = 0
	file_desc = open(seq_file, "r+w")
	lock_file(file_desc)
	data = file_desc.readlines()
	#print "received " + str(seq_no)
        for line in data:
		line_counter += 1
		match = re.findall('(\d+),(\w)\n',line)
		if match:
			read_seq = match[0][0]
			status = match[0][1]
			if int(read_seq) == int(seq_no) and status == 'A' and line_counter == 1:
				make_change = 1
				break
			elif int(read_seq) < int(seq_no) and status != 'D':
				break
			elif int(read_seq) == int(seq_no) and status == 'A' and line_counter > 1:
				make_change = 1
				break
	if make_change == 1:
		if data[int(seq_no)] == seq_no + ",A\n":
	        	data[int(seq_no)] = seq_no + ",D\n"
		new_data = ''.join(data)
	        file_desc.seek(0)
		file_desc.truncate()	
		file_desc.write(new_data)
        file_desc.close()


'''validate the ack message recieved from the server'''
def validate_recv_msg(msg):
	seq_no = str(int(msg[0:32],2))
	pad = msg[32:48]
	ack_ind = msg[48:]
	if pad == ('0' * 16) and ack_ind == ('10' * 8):
		return seq_no
	return -1

'''handle the timeout of the packet mark the active packet to null
to send the packet again'''
def handle_timer(send_seq_no,seq_file):
	child_process = os.fork()
	if child_process == 0:
		p = psutil.Process(os.getpid())
		p.set_nice(15)
		#print 'priority-handle timeout' + str(p.nice)
		time.sleep(0.5)
		file_desc = open(seq_file,'r+w')
		lock_file(file_desc)
		update_seq_status = -1
		data = file_desc.readlines()
		for line in data:
			match = re.findall('(\d+),(\w)\n',line)
			if match:
				if send_seq_no == str(match[0][0]):
					if str(match[0][1]) == 'D':
						#print "Seq:" + send_seq_no + " ACK"
						break
					elif str(match[0][1]) == 'A':
						print "Timeout, sequence number =:" + send_seq_no
						update_seq_status = 1
						break
					else:
						break
		if update_seq_status == 1:
			if data[int(send_seq_no)] == send_seq_no + ",A\n":
				data[int(send_seq_no)] = send_seq_no + ",\n"
			new_data = ''.join(data)
			file_desc.seek(0)
			file_desc.truncate()
			file_desc.write(new_data)
		file_desc.close()
		os._exit(0)		

'''check if all the packets have been acknowledged, if so exit the process'''
def check_transfer_status(seq_file):
        file_transfer = 0
        file_desc = open(seq_file,'r')
	lock_file(file_desc)
        for line in file_desc:
		if line != '\n':
	        	status = re.findall('\d+,([D])\n',line)
        	        if not status:
				file_transfer = -1
				break
	file_desc.close()
        return file_transfer

'''create the sequence file which implements the sliding window'''
def create_seq_file(file_to_send,mss_val,seq_file_name):
	if os.path.exists(file_to_send):
		if os.path.getsize(file_to_send) > 0:
                        if os.path.exists(seq_file_name):
				os.remove(seq_file_name)
            		seq_file_desc = open(seq_file_name,'a')
            		sequence = 0
			seq_file_desc.write(str(sequence) + ',\n')
            		with open(file_to_send, "rb") as file_desc:
				while 1:
					position = (sequence + 1) * mss_val
			                file_desc.seek(position,0)
                    			byte_data = file_desc.read(1)
                    			if not byte_data:
						break
                    			sequence = sequence + 1
                    			seq_file_desc.write(str(sequence) + ',\n')                    
            		file_desc.close()
            		seq_file_desc.close()
            		return '1'
		else:
			return '-1'
	else:
		return '-2'



'''''''''''''''''Main Program'''''''''''
start_time = time.time()

#print sys.argv
if(len(sys.argv) == 7):
	server_host = sys.argv[1]
	port = int(sys.argv[2])
	file_to_send = sys.argv[3]
	window_size = int(sys.argv[4])
	mss_val = int(sys.argv[5])
	seq_file = sys.argv[6]
else:
	print "Wrong set of arguments passed"
	exit(0)

seq_file_status = create_seq_file(file_to_send,mss_val,seq_file)

if seq_file_status == '-1':
	print "File to be transferred is empty. Exiting process..."
	os._exit(0)
elif seq_file_status == '-2':
	print "File to be transferred does not exist. Exiting process..."
	os._exit(0)

max_buff = 65535

client_socket = socket(AF_INET,SOCK_DGRAM)

'''create new process to handle recv ACK's from server'''
recv_process(client_socket,seq_file)

'''main client process handling sending of files'''
while 1:
	p = psutil.Process(os.getpid())
	p.set_nice(5)
	#print 'priority-main process' + str(p.nice)
        transfer_status = check_transfer_status(seq_file)
	if transfer_status == 0:
                print "File transfer completed."
		print "Total time taken(sec):" + str(time.time() - start_time)
                break

	send_seq_no = get_seq_no(window_size,seq_file)
	if send_seq_no > -1:
		'''now mark the sequence no as active'''
                mark_seqno_active(send_seq_no,seq_file)
		#print "made active:" + str(send_seq_no)
		'''generate the packet from the corresponding file and send'''
		msg_to_send = rdt_send(file_to_send,mss_val,int(send_seq_no))
		client_socket.sendto(msg_to_send,(server_host,port))
		#print "sent active:" + str(send_seq_no)
		handle_timer(send_seq_no,seq_file)
		#time.sleep(2)
print "Exiting from process..."
client_socket.close()
