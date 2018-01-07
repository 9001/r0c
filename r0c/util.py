# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import threading
import time
import sys

from .config import *

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
		
		# escape sequences can never contain ESC;
		# treat pend as regular text if so
		if ch == u'\033' and pend:
			clen += len(pend)
			ret += pend
			counting = True
			pend = None
		
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



# adapted from trunc
def visual_length(txt):
	clen = 0
	pend = None
	counting = True
	az = 'abcdefghijklmnopqrstuvwxyz'
	for ch in txt:
		
		# escape sequences can never contain ESC;
		# treat pend as regular text if so
		if ch == u'\033' and pend:
			clen += len(pend)
			counting = True
			pend = None
		
		if not counting:
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
				pend = None
			else:
				if ch == u'\033':
					pend = u'{0}'.format(ch)
				else:
					clen += 1
	return clen



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



def visualize_all_unicode_codepoints_as_utf8():
	stats = [0]*256
	nmax = sys.maxunicode + 1
	print('collecting all codepoints until {0}d, 0x{1:x}'.format(
		nmax, nmax))
	
	if PY2:
		to_unicode = unichr
		from_char = ord
	else:
		to_unicode = chr
		from_char = int
	
	for n in range(nmax):
		if n % 0x10000 == 0:
			print('at codepoint {0:6x} of {1:6x},  {2:5.2f}%'.format(
				n, nmax, (100.0 * n) / nmax))
		ch = to_unicode(n)
		
		try:
			bs = ch.encode('utf-8')
		except:
			# python2 allows encoding ud800 as \xed\xa0\x80 which is an illegal sequence in utf8;
			# python -c "for x in unichr(0xd800).encode('utf-8'): print '{0:2x}'.format(ord(x))"
			continue
		
		for b in bs:
			stats[from_char(b)] += 1

	print()
	for i, n in enumerate(stats):
		v = n
		if v == 0:
			v = 'illegal value'
		elif v == 1:
			v = 'single-use value'
		print('byte 0x{0:2x} occurences: {1}'.format(i, v))
	print()

#visualize_all_unicode_codepoints_as_utf8()



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
