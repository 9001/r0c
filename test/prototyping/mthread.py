# test case for multithreaded access to the print() builtin,
# the native print appears to have a mutex covering the main message
# but the 'end' variable is tacked on outside of it
# meaning you might lose the newline to a pending message

import threading
import time

nthr = 0
msg = '\r\n'.join('{0}a'.format(' '*(x*2)) for x in range(30))

p_mutex = threading.Lock()
def p(*args, **kwargs):
	with p_mutex:
		print(*args, **kwargs)

def worker():
	global nthr
	nthr += 1
	while True:
		p(nthr)
		p(msg, end='1234567890\r\n')

for n in range(4):
	thr = threading.Thread(target=worker)
	thr.daemon = True
	thr.start()

time.sleep(1)
