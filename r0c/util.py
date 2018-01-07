if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import threading
import time
import sys

from config import *

PY2 = (sys.version_info[0] == 2)

def fmt():
	return time.strftime('%d/%m/%Y, %H:%M:%S')

def num(c):
	try:
		return int(c)
	except:
		return None

def b2hex(data):
	if PY2:
		return ' '.join(map(lambda b: format(ord(b), "02x"), data))
	else:
		if type(data) is str:
			return ' '.join(map(lambda b: format(ord(b), "02x"), data))
		else:
			return ' '.join(map(lambda b: format(b, "02x"), data))

def hexdump(pk, prefix=''):
	lpk = len(pk)
	ofs = 0
	hexofs = 0
	hexlen = 0
	hexstr = ''
	ascstr = ''
	ascstr_width = int(HEX_WIDTH * 100 / 32)  # 32h = 100a, 16h = 50a
	while ofs < lpk:
		hexstr += b2hex(pk[ofs:ofs+8])
		hexstr += '  '
		if PY2:
			ascstr += ''.join(map(lambda b: b if ord(b) >= 0x20 and ord(b) < 0x7f else '.', pk[ofs:ofs+8]))
		else:
			ascstr += ''.join(map(lambda b: chr(b) if b >= 0x20 and b < 0x7f else '.', pk[ofs:ofs+8]))
		ascstr += ' '
		hexlen += 8
		ofs += 8
		
		if hexlen >= HEX_WIDTH or ofs >= lpk:
			print('{0}{1:8x}  {2}{3}{4}'.format(
				prefix, hexofs, hexstr,
				' '*(ascstr_width-len(hexstr)), ascstr))
			hexofs = ofs
			hexstr = ''
			hexlen = 0
			ascstr = ''

def trunc(txt, maxlen):
	clen = 0
	ret = u''
	pend = None
	counting = True
	az = 'abcdefghijklmnopqrstuvwxyz'
	for ch in txt:
		if not counting:
			ret += ch
			if ch in az:
				counting = True
		else:
			if pend:
				pend += ch
				if pend.startswith(u'\033['):
					counting = False
				else:
					clen += len(pend)
					counting = True
				ret += pend
				pend = None
			else:
				if ch == u'\033':
					pend = u'{0}'.format(ch)
				else:
					ret += ch
					clen += 1
		if clen >= maxlen:
			return ret
	return ret



B35_CHARS = tuple('0123456789abcdefghijkmnopqrstuvwxyz')
B35_ATLAS = dict((c, i) for i, c in enumerate(B35_CHARS))
B35_BASE = len(B35_CHARS)
def b35enc(number):
	if not number:
		return B35_CHARS[0]

	prefix = ''
	if number < 0:
		prefix = '-'
		number = abs(number)

	ret = ''
	while number:
		number, rem = divmod(number, B35_BASE)
		ret = B35_CHARS[rem] + ret

	return prefix + ret

def b35dec(b35str):
	factor = 1
	if b35str.startswith('-'):
		b35str = b35str[1:]
		factor = -1

	ret = 0
	for c in b35str:
		ret = ret * B35_BASE + B35_ATLAS[c]

	return factor * ret



class Printer(object):
	
	def __init__(self):
		self.mutex = threading.Lock()
	
	def p(self, data, usercount=None):
		with self.mutex:
			if len(data) < 13:
				data += ' ' * 13
			if usercount:
				sys.stdout.write('%s\n     %d users\r' % (data, usercount))
			else:
				sys.stdout.write('%s\n' % (data,))
			sys.stdout.flush()



def signal_handler(signal, frame):
	print('\n-(!) SHUTDOWN-')
	sys.exit(0)
