# -*- coding: utf-8 -*-
from __future__ import print_function
from .__init__ import *
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

import traceback
import threading
import struct
import time
import sys
import os
import platform

from .config import *



print_mutex = threading.Lock()
if PY2:
	import __builtin__
	def print(*args, **kwargs):
		args = list(args)
		try:
			if WINDOWS and u'\033' in args[0]:
				args[0] = strip_ansi(args[0])
		except: pass
		
		with print_mutex:
			t = time.strftime('%H%M%S ')
			__builtin__.print(t + str(args[0] if args else u''
				).replace(u'\n', u'\n'+t), *args[1:], **kwargs)
else:
	import builtins
	def print(*args, **kwargs):
		args = list(args)
		try:
			if WINDOWS and u'\033' in args[0]:
				args[0] = strip_ansi(args[0])
		except: pass
		
		with print_mutex:
			t = time.strftime('%H%M%S ')
			builtins.print(t + str(args[0] if args else u''
				).replace(u'\n', u'\n'+t), *args[1:], **kwargs)

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

def hexdump(pk, prefix='', file=None):
	if file is not None:
		line_fmt = u'{0} {2}{3}{4}'
		hex_width = 4
		blk_width = 4
	else:
		line_fmt = u'{0}{1:8x}  {2}{3} {4}'
		hex_width = HEX_WIDTH
		blk_width = 8

	lpk = len(pk)
	ofs = 0
	hexofs = 0
	hexlen = 0
	hexstr = ''
	ascstr = ''
	ascstr_width = int(hex_width * 100 / 32.0 - 0.5)  # 32h = 100a, 16h = 50a
	while ofs < lpk:
		hexstr += b2hex(pk[ofs:ofs+blk_width])
		hexstr += ' '
		if PY2:
			ascstr += ''.join(map(lambda b: b if ord(b) >= 0x20 and ord(b) < 0x7f else '.', pk[ofs:ofs+blk_width]))
		else:
			ascstr += ''.join(map(lambda b: chr(b) if b >= 0x20 and b < 0x7f else '.', pk[ofs:ofs+blk_width]))
		hexlen += blk_width
		ofs += blk_width
		
		if hexlen >= hex_width or ofs >= lpk:
			txt = line_fmt.format(prefix, hexofs, hexstr,
				u' '*(ascstr_width-len(hexstr)), ascstr)
			
			if file is not None:
				file.write((txt + u'\n').encode('utf-8'))
			else:
				print(txt)

			hexofs = ofs
			hexstr = ''
			hexlen = 0
			ascstr = ''
		else:
			hexstr += ' '
			ascstr += ' '

def test_hexdump():
	try: from StringIO import StringIO as bio
	except: from io import BytesIO as bio
	
	v = b''
	for n in range(5):
		print()
		v += b'a'
		fobj = bio()
		hexdump(v, '>', fobj)
		print(fobj.getvalue().decode('utf-8').rstrip('\n') + '$')
		fobj.close()
	
	v = b''
	for n in range(18):
		print()
		v += b'a'
		hexdump(v, '>')
	
	sys.exit(0)



azAZ = u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

def trunc(txt, maxlen):
	eoc = azAZ
	ret = u''
	clen = 0
	pend = None
	counting = True
	for input_ofs, ch in enumerate(txt):
		
		# escape sequences can never contain ESC;
		# treat pend as regular text if so
		if ch == u'\033' and pend:
			clen += len(pend)
			ret += pend
			counting = True
			pend = None
		
		if not counting:
			ret += ch
			if ch in eoc:
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
			return [ret, txt[input_ofs:]]
	
	return [ret, u'']



# adapted from trunc
def strip_ansi(txt):
	eoc = azAZ
	ret = u''
	pend = None
	counting = True
	for ch in txt:
		
		# escape sequences can never contain ESC;
		# treat pend as regular text if so
		if ch == u'\033' and pend:
			ret += pend
			counting = True
			pend = None
		
		if not counting:
			if ch in eoc:
				counting = True
		else:
			if pend:
				pend += ch
				if pend.startswith(u'\033['):
					counting = False
				else:
					ret += pend
					counting = True
				pend = None
			else:
				if ch == u'\033':
					pend = u'{0}'.format(ch)
				else:
					ret += ch
	return ret



# adapted from trunc
def visual_length(txt):
	eoc = azAZ
	clen = 0
	pend = None
	counting = True
	for ch in txt:
		
		# escape sequences can never contain ESC;
		# treat pend as regular text if so
		if ch == u'\033' and pend:
			clen += len(pend)
			counting = True
			pend = None
		
		if not counting:
			if ch in eoc:
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



# 83% the speed of visual_length,
# good enough to stop maintaining it and swap w/ len(this)
def visual_indices(txt):
	eoc = azAZ
	ret = []
	pend_txt = None
	pend_ofs = []
	counting = True
	for n, ch in enumerate(txt):
		
		# escape sequences can never contain ESC;
		# treat pend as regular text if so
		if ch == u'\033' and pend_txt:
			ret.extend(pend_ofs)
			counting = True
			pend_txt = None
			pend_ofs = []
		
		if not counting:
			if ch in eoc:
				counting = True
		else:
			if pend_txt:
				pend_txt += ch
				pend_ofs.append(n)
				if pend_txt.startswith(u'\033['):
					counting = False
				else:
					ret.extend(pend_ofs)
					counting = True
				pend_txt = None
				pend_ofs = []
			else:
				if ch == u'\033':
					pend_txt = u'{0}'.format(ch)
					pend_ofs = [n]
				else:
					ret.append(n)
	return ret



def sanitize_ctl_codes(aside):
	plain = u''
	for pch in aside:
		nch = ord(pch)
		#print('read_cb inner  {0} / {1}'.format(b2hex(pch.encode('utf-8', 'backslashreplace')), nch))
		if nch < 0x20 and nch != 0x0b and nch != 0x0f:
			print('substituting non-printable \\x{0:02x}'.format(nch))
			plain += u'?'
		else:
			plain += pch
	return plain



FOREGROUNDS = {}
for luma, chars in enumerate([u'01234567',u'89abcdef']):
	for n, ch in enumerate(chars):
		FOREGROUNDS[ch] = u'\033[{0};3{1}'.format(luma, n)

BACKGROUNDS = {}
for n, ch in enumerate(u'01234567'):
	BACKGROUNDS[ch] = u';4{0}'.format(n)

def convert_color_codes(txt, preview=False):
	foregrounds = FOREGROUNDS
	backgrounds = BACKGROUNDS
	scan_from = 0
	while txt:
		ofs = txt.find(u'\x0b', scan_from)
		if ofs < 0:
			break
		
		scan_from = ofs + 1

		fg = None
		if len(txt) > ofs + 1:
			fg = txt[ofs+1]
		
		bg = None
		if len(txt) > ofs + 3 and txt[ofs+2] == u',':
			bg = txt[ofs+3]
		
		if fg in foregrounds:
			fg = foregrounds[fg]
		else:
			fg = None
			bg = None  # can't set bg without valid fg
		
		if bg in backgrounds:
			bg = backgrounds[bg]
		else:
			bg = None

		resume_txt = ofs + 1
		if fg:
			resume_txt += 1
			scan_from = len(fg) + 1
		if bg:
			resume_txt += 2
			scan_from += len(bg)

		preview_k = u''
		if preview:
			resume_txt = ofs + 1
			if fg:
				preview_k = u'K'

		if fg and bg:
			txt = u'{0}{1}{2}m{3}{4}'.format(
				txt[:ofs], fg, bg, preview_k, txt[resume_txt:])
		elif fg:
			txt = u'{0}{1}m{2}{3}'.format(
				txt[:ofs], fg, preview_k, txt[resume_txt:])
		else:
			txt = u'{0}K{1}'.format(
				txt[:ofs], txt[resume_txt:])

	scan_from = 0
	while txt:
		ofs = txt.find(u'\x0f', scan_from)
		if ofs < 0:
			break

		scan_from = ofs + 1
		txt = u'{0}\033[0m{2}{1}'.format(
			txt[:ofs], txt[scan_from:],
			u'O' if preview else u'')
	
	return txt



#B35_CHARS = tuple(u'0123456789abcdefghijkmnopqrstuvwxyz')
B35_CHARS = tuple(u'abcdefghijkmnopqrstuvwxyz')
B35_ATLAS = dict((c, i) for i, c in enumerate(B35_CHARS))
B35_BASE = len(B35_CHARS)
def b35enc(number):
	if not number:
		return B35_CHARS[0]

	prefix = u''
	if number < 0:
		prefix = u'-'
		number = abs(number)

	ret = u''
	while number:
		number, rem = divmod(number, B35_BASE)
		ret = B35_CHARS[rem] + ret

	return prefix + ret

def b35dec(b35str):
	factor = 1
	if b35str.startswith(u'-'):
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



def prewrap(txt, maxlen):
	words = txt.split()
	ret = []
	for word in words:
		if len(word) < maxlen or visual_length(word) < maxlen:
			ret.append(word)
		else:
			while visual_length(word) >= maxlen:
				ret.append(word[:maxlen-1] + u'-')
				word = word[maxlen-1:]
			if word:
				ret.append(word)
	return ret



def whoops(extra=None):
	msg = """\
             __
   _      __/ /_  ____  ____  ____  _____
  | | /| / / __ \/ __ \/ __ \/ __ \/ ___/
  | |/ |/ / / / / /_/ / /_/ / /_/ (__  )
  |__/|__/_/ /_/\____/\____/ .___/____/
                          /_/"""
	exc = traceback.format_exc()
	if exc.startswith('None'):
		exc = ''.join(traceback.format_stack()[:-1])
	msg = '{0}\r\n{1}\r\n{2}</stack>'.format(
		msg, exc.rstrip(), '-'*64)
	print(msg)
	if extra:
		print('  {0}\n{1}\n'.format(extra, '-'*64))



def t_a_a_bt():
	ret = []
	for tid, stack in sys._current_frames().items():
		ret.append(u'\r\nThread {0} {1}'.format(tid, '='*64))
		for fn, lno, func, line in traceback.extract_stack(stack):
			ret.append(u'  File "{0}", line {1}, in {2}'.format(fn, lno, func))
			if line:
				ret.append(u'    {0}'.format(line.strip()))
	return u'\r\n'.join(ret)

thread_monitor_enabled = False
def monitor_threads():
	global thread_monitor_enabled
	if thread_monitor_enabled:
		return
	thread_monitor_enabled = True

	def stack_collector():
		while True:
			print('capturing stack')
			time.sleep(5)
			txt = t_a_a_bt()
			with open('r0c.stack', 'wb') as f:
				f.write(txt.encode('utf-8'))

	thr = threading.Thread(target=stack_collector, name='stk_col')
	thr.daemon = True
	thr.start()



def host_os():
	py_ver = '.'.join([str(x) for x in sys.version_info])
	ofs = py_ver.find('.final.')
	if ofs > 0:
		py_ver = py_ver[:ofs]

	bitness = struct.calcsize('P') * 8
	host_os = platform.system()
	return '{0} on {1}{2}'.format(py_ver, host_os, bitness)



def compat_chans_in_root():
	bad_dirs = []
	good_dirs = ['pm','chan','wire']
	for (dirpath, dirnames, filenames) in os.walk(EP.log):
		for d in dirnames:
			if d not in good_dirs:
				bad_dirs.append(d)
		break

	if bad_dirs:
		print()
		print('== performing upgrade in 5 seconds ==')
		print()
		print('Will move the following directories from [log] to [log/chan]:')
		print(', '.join(bad_dirs))
		print()
		print('PRESS CTRL-C TO ABORT')
		for n in range(5):
			print('{0} ...'.format(5-n))
			time.sleep(1)
	
		for d in bad_dirs:
			os.rename(
				'{0}{1}'.format(EP.log, d),
				'{0}chan/{1}'.format(EP.log, d))

		print('upgrade done \\o/')
		print()
