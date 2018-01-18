#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function


import os
import sys
import platform
import random
import struct
import time
import json
try:
	import cPickle as pickle  # py2
except:
	import pickle  # py3


class Message(object):
	def __init__(self, user, ts, txt):
		self.user = user        # str username
		self.ts   = ts          # int timestamp
		self.txt  = txt         # str text


def result(desc, sec, sec2, mul, comp_t, base_t, fn=None):
	sz = os.path.getsize(fn) if fn else 'x'
	print(u'{0:24} {1:8.3f}s  {2:8.3f}s  {3:8.3f} ({4:.3f},{5:.3f})  {6:9} byte'.format(
		desc, sec, sec2, mul, comp_t, base_t, sz))


""" run a test function, compare time against comp_t after subtracting base_t """
def run(func, write_to, comp_t=None, base_t=None):
	mtd = 99999999
	desc = func.__name__[2:]
	is_windows = platform.system() == 'Windows'
	if not is_windows:
		print()

	best = []
	for iteration in range(2):
		t0 = time.time()
		func(write_to)
		td = time.time() - t0
		
		base_tv = base_t or td
		comp_tv = comp_t or td
		rel_tv = td - base_tv
		mul = rel_tv / comp_tv if comp_t else 1
		if mtd > td:
			mtd = td
			best = [desc, td, rel_tv, mul, comp_tv, base_tv, write_to]
			if not is_windows:
				print('\033[A', end='')
				result(*best)
	
	if is_windows:
		result(*best)

	return [ desc, write_to, mtd ]


def gen_sentence():
	letters = u'宇多田ヒカル桜流しABCDEFGHIJKLMNOPQRSTUVWXYZ\\\'\'\'"/abcdefghijklmnopqrstuvwxyz        '
	ret = u''
	retlen = random.randint(4, 64)
	for n in range(retlen):
		ret += random.choice(letters)
	return ret.strip()


users = []
letters = u'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
for n in range(12):
	ret = u''
	for n in range(8):
		ret += random.choice(letters)
	users.append(ret)


def stream_txt():
	with open('txt', 'rb') as f:
		for ln in f:
			yield ln.decode('utf-8').rstrip()


def stream_msgs():
	iuser = 0
	with open('txt', 'rb') as f:
		for n, ln in enumerate(f):
			txt = ln.decode('utf-8').rstrip()
			mod = n % 32
			if mod == 31:
				mid = int(len(txt) / 2)
				txt = u'{0}\n{1}'.format(txt[:mid], txt[mid:])
			if mod == 15:
				mid = int(len(txt) / 2)
				txt = u'{0}\r{1}'.format(txt[:mid], txt[mid:])

			yield Message(users[iuser], n, txt)
			iuser += 1
			if iuser >= len(users):
				iuser = 0


def t_gen_txt_file(dontcare):
	with open('txt', 'wb') as f:
		for n in range(1048576):
			if n % 8192 == 0:
				print('{0}  {1:.2f}%'.format(n, n*100.0/1048576))
			f.write(u'{0}\n'.format(gen_sentence()).encode('utf-8'))

if not os.path.isfile('txt'):
	run(t_gen_txt_file, 'txt')


py_ver = '.'.join([str(x) for x in sys.version_info])
bitness = struct.calcsize('P') * 8
host_os = platform.system()
print('\n\n{0} // {1}{2} // Serialization'.format(py_ver, host_os, bitness))


### takeaways:
#
# enumerate(list)  is slower than looking up each item in a dict
#
# chaining .replace beats most alternatives
#
# checking whether a string contains a character before trying to replace it saves surprisingly little time
#
# iterating over characters in source and conditionally writing ch or \ch is ~30% the speed of chained .replace
#
# loading global variables into a method before repeatedly using it saves a tiny amount of time
#


def t_stream_utf8(fn):
	for ln in stream_txt():
		pass

td_utf8 = run(t_stream_utf8, 'txt')[2]
base_t = td_utf8
comp_t = td_utf8



def t_stream_msgs(fn):
	for msg in stream_msgs():
		pass

td_msgs = run(t_stream_msgs, 'txt', None, comp_t)[2]
base_t = td_msgs
comp_t = td_msgs



r_from = u'\\\'\r\n'
r_to = [ u'\\\\', u'\\\'', u'\\r', u'\\n' ]
r_map = {
	u'\\': u'\\\\',
	u'\'': u'\\\'',
	u'\r': u'\\r',
	u'\n': u'\\n'
}



# py[23] identical:  1.00  1.00
#
def t_chain_replace(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, msg.txt.\
				replace(u'\\', u'\\\\').\
				replace(u'\'', u'\\\'').\
				replace(u'\r', u'\\r').\
				replace(u'\n', u'\\n')).\
				encode('utf-8'))

td_chain = run(t_chain_replace, 's_esc1', None, comp_t)[2]
comp_t = td_chain - base_t



# py[23] identical:  1.49  1.40
#
def t_enumerate_replace(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for n, bad in enumerate(r_from):
				txt = txt.replace(bad, r_to[n])
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_enumerate_replace, 's_esc2a', base_t, comp_t)



# py[23] identical:  1.41  1.22
#
def t_foreach_dict_replace(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for bad in r_from:
				txt = txt.replace(bad, r_map[bad])
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_foreach_dict_replace, 's_esc2b', base_t, comp_t)



# py[23] identical:  1.71  1.69
#
def t_foreach_idx_replace(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for bad in r_from:
				txt = txt.replace(bad, r_to[r_from.index(bad)])
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_foreach_idx_replace, 's_esc2c', base_t, comp_t)



# py[23] identical:  1.27  1.10
#
def t_enumerate_replaceif(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for n, bad in enumerate(r_from):
				if bad in txt:
					txt = txt.replace(bad, r_to[n])
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_enumerate_replaceif, 's_esc3', base_t, comp_t)



# py[23] identical:  1.13  0.91
#
def t_replaceif_dict(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for bad in r_from:
				if bad in txt:
					txt = txt.replace(bad, r_map[bad])
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_replaceif_dict, 's_esc3b', base_t, comp_t)



# py[23] identical:  1.13  0.89
#
def t_replaceif_dict_loc(fn):
	with open(fn, 'wb') as f:
		lr_from = r_from
		lr_map = r_map
		for msg in stream_msgs():
			txt = msg.txt
			for bad in lr_from:
				if bad in txt:
					txt = txt.replace(bad, lr_map[bad])
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_replaceif_dict_loc, 's_esc3c', base_t, comp_t)



# py[23] identical:  3.19  3.19
#
def t_condwrite_always_dict(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = u''
			for ch in msg.txt:
				if ch in r_from:
					txt += r_map[ch]
				else:
					txt += ch
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_condwrite_always_dict, 's_esc4', base_t, comp_t)



# py[23] identical:  3.06  2.81
#
def t_condwrite_ifneed_list(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for bad in r_from:
				if bad in msg.txt:
					txt = u''
					for ch in msg.txt:
						if ch in r_from:
							txt += r_map[ch]
						else:
							txt += ch
					break
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_condwrite_ifneed_list, 's_esc5', base_t, comp_t)



# py[23] identical:  3.38  2.99
#
def t_condwrite_ifneed_dict(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			txt = msg.txt
			for bad in r_from:
				if bad in msg.txt:
					txt = u''
					for ch in msg.txt:
						if ch in r_map:
							txt += r_map[ch]
						else:
							txt += ch
					break
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, txt).\
				encode('utf-8'))

run(t_condwrite_ifneed_dict, 's_esc5b', base_t, comp_t)



# Differ:  0.92  0.57
#
def t_msgtxt_repr(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			f.write(u'{0} {1} {2}\n'.format(
				msg.ts, msg.user, repr(msg.txt)).\
				encode('utf-8'))

run(t_msgtxt_repr, 'txt_repr', base_t, comp_t)



# Differ:  ?  ?
#
def t_fakelist_repr(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			f.write(u'[{0}, u\'{1}\', {2}]\n'.format(
				msg.ts, msg.user, repr(msg.txt)).\
				encode('utf-8'))

run(t_fakelist_repr, 'lst_repr_f', base_t, comp_t)



# Differ:  1.07  0.83
# 
def t_list_repr(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			f.write(u'{0}\n'.format(
				repr([msg.ts, msg.user, msg.txt])).\
				encode('utf-8'))

run(t_list_repr, 'lst_repr', base_t, comp_t)



# NG:  1.26  1.35
#
def t_uesc(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			f.write(u'{0}\n'.format(
				u'{0} {1} {2}'.format(
					msg.ts, msg.user, msg.txt).\
					encode('unicode_escape')).\
				encode('utf-8'))

run(t_uesc, 'uesc', base_t, comp_t)



# Too slow + insecure:  3.15  2.09
#
def t_pickle2(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			pickle.dump(msg, f, 2)

run(t_pickle2, 'p2', base_t, comp_t)



# py[23] identical:  2.38  2.41
#
def t_json_str(fn):
	with open(fn, 'wb') as f:
		for msg in stream_msgs():
			f.write(u'{0}\n'.format(json.dumps([msg.ts, msg.user, msg.txt])).encode('utf-8'))

run(t_json_str, 'json1', base_t, comp_t)



# py[23] different + 2slow:  5.5  5.6
#
def t_json_fh(fn):
	with open(fn, 'w') as f:
		for msg in stream_msgs():
			json.dump([msg.ts, msg.user, msg.txt], f)

run(t_json_fh, 'json2', base_t, comp_t)





"""
2.6.0.final.0 // Windows32 // Serialization
gen_txt_file               28.487s     0.000s     1.000                 45024723 byte
stream_utf8                 1.399s     0.000s     1.000 (1.399,1.399)   45024723 byte
stream_msgs                 2.413s     1.014s     1.000 (2.413,1.399)   45024723 byte
chain_replace               7.011s     4.598s     1.000 (7.011,2.413)   63772299 byte
enumerate_replace           8.774s     4.176s     1.731 (2.413,4.598)   63772299 byte
foreach_dict_replace        8.316s     3.718s     1.541 (2.413,4.598)   63772299 byte
foreach_idx_replace         9.026s     4.428s     1.835 (2.413,4.598)   63772299 byte
enumerate_replaceif         8.295s     3.697s     1.532 (2.413,4.598)   63772299 byte
replaceif_dict              7.925s     3.327s     1.379 (2.413,4.598)   63772299 byte
replaceif_dict_loc          7.913s     3.315s     1.374 (2.413,4.598)   63772299 byte
condwrite_always_dict      13.482s     8.884s     3.682 (2.413,4.598)   63772299 byte
condwrite_ifneed_list      13.424s     8.826s     3.658 (2.413,4.598)   63772299 byte
condwrite_ifneed_dict      13.714s     9.116s     3.778 (2.413,4.598)   63772299 byte
msgtxt_repr                 7.197s     2.599s     1.077 (2.413,4.598)   78927560 byte
fakelist_repr               7.248s     2.650s     1.098 (2.413,4.598)   86267592 byte
list_repr                   7.717s     3.119s     1.293 (2.413,4.598)   86267592 byte
uesc                        8.259s     3.661s     1.517 (2.413,4.598)   75184474 byte
pickle2                    13.299s     8.701s     3.606 (2.413,4.598)  128844837 byte
json_str                   17.263s    12.665s     5.249 (2.413,4.598)   84047968 byte
json_fh                    15.216s    10.618s     4.400 (2.413,4.598)   82999392 byte

3.6.2.final.0 // Windows64 // Serialization
gen_txt_file               42.314s     0.000s     1.000                 45031335 byte
stream_utf8                 0.780s     0.000s     1.000 (0.780,0.780)   45024723 byte
stream_msgs                 1.920s     1.141s     1.000 (1.920,0.780)   45024723 byte
chain_replace               5.521s     3.600s     1.000 (5.521,1.920)   63772299 byte
enumerate_replace           6.637s     3.037s     1.581 (1.920,3.600)   63772299 byte
foreach_dict_replace        6.088s     2.487s     1.295 (1.920,3.600)   63772299 byte
foreach_idx_replace         7.056s     3.455s     1.799 (1.920,3.600)   63772299 byte
enumerate_replaceif         6.056s     2.455s     1.279 (1.920,3.600)   63772299 byte
replaceif_dict              5.555s     1.954s     1.018 (1.920,3.600)   63772299 byte
replaceif_dict_loc          5.599s     1.999s     1.041 (1.920,3.600)   63772299 byte
condwrite_always_dict       9.801s     6.201s     3.229 (1.920,3.600)   63772299 byte
condwrite_ifneed_list       9.608s     6.008s     3.128 (1.920,3.600)   63772299 byte
condwrite_ifneed_dict       9.960s     6.359s     3.312 (1.920,3.600)   63772299 byte
msgtxt_repr                 4.681s     1.080s     0.563 (1.920,3.600)   65040655 byte
fakelist_repr               4.778s     1.177s     0.613 (1.920,3.600)   72380687 byte
list_repr                   5.337s     1.736s     0.904 (1.920,3.600)   71332111 byte
uesc                        6.562s     2.962s     1.542 (1.920,3.600)   84223875 byte
pickle2                     9.625s     6.025s     3.138 (1.920,3.600)  138282195 byte
json_str                    9.394s     5.793s     3.017 (1.920,3.600)   84047968 byte
json_fh                    19.304s    15.704s     8.178 (1.920,3.600)   82999392 byte

py2.7.13 // debian64
gen lines                  16.369s
stream_utf8                 0.817s     0.000s     1.000 (0.817,0.817)   45012467 byte
stream_msgs                 1.409s     0.592s     1.000 (1.409,0.817)   45012467 byte
chain_replace               3.641s     2.232s     1.000 (3.641,1.409)   63760646 byte
enumerate_replace           4.327s     2.095s     1.487 (1.409,2.232)   63760646 byte
foreach_dict_replace        4.213s     1.981s     1.406 (1.409,2.232)   63760646 byte
foreach_idx_replace         4.638s     2.406s     1.707 (1.409,2.232)   63760646 byte
enumerate_replaceif         4.021s     1.789s     1.269 (1.409,2.232)   63760646 byte
replaceif_dict              3.817s     1.585s     1.125 (1.409,2.232)   63760646 byte
replaceif_dict_loc          3.820s     1.588s     1.127 (1.409,2.232)   63760646 byte
condwrite_always_dict       6.726s     4.494s     3.189 (1.409,2.232)   63760646 byte
condwrite_ifneed_list       6.541s     4.309s     3.058 (1.409,2.232)   63760646 byte
condwrite_ifneed_dict       6.999s     4.767s     3.382 (1.409,2.232)   63760646 byte
msgtxt_repr                 3.525s     1.293s     0.917 (1.409,2.232)   78921907 byte
list_repr                   3.737s     1.505s     1.068 (1.409,2.232)   86261939 byte
uesc                        4.005s     1.773s     1.258 (1.409,2.232)   75177292 byte
pickle2                     6.674s     4.442s     3.152 (1.409,2.232)  128832607 byte
json_str                    5.591s     3.359s     2.383 (1.409,2.232)   84040832 byte
json_fh                     9.970s     7.738s     5.490 (1.409,2.232)   82992256 byte

py3.5.3 // debian64
gen lines                  26.677s
stream_utf8                 0.551s     0.000s     1.000 (0.551,0.551)   45012467 byte
stream_msgs                 1.298s     0.747s     1.000 (1.298,0.551)   45012467 byte
chain_replace               3.204s     1.906s     1.000 (3.204,1.298)   63760646 byte
enumerate_replace           3.727s     1.821s     1.403 (1.298,1.906)   63760646 byte
foreach_dict_replace        3.488s     1.582s     1.219 (1.298,1.906)   63760646 byte
foreach_idx_replace         4.098s     2.192s     1.689 (1.298,1.906)   63760646 byte
enumerate_replaceif         3.330s     1.424s     1.097 (1.298,1.906)   63760646 byte
replaceif_dict              3.088s     1.182s     0.911 (1.298,1.906)   63760646 byte
replaceif_dict_loc          3.064s     1.159s     0.893 (1.298,1.906)   63760646 byte
condwrite_always_dict       6.041s     4.136s     3.186 (1.298,1.906)   63760646 byte
condwrite_ifneed_list       5.556s     3.651s     2.813 (1.298,1.906)   63760646 byte
condwrite_ifneed_dict       5.783s     3.877s     2.987 (1.298,1.906)   63760646 byte
msgtxt_repr                 2.647s     0.742s     0.571 (1.298,1.906)   65030226 byte
list_repr                   2.983s     1.078s     0.830 (1.298,1.906)   71321682 byte
uesc                        3.656s     1.751s     1.349 (1.298,1.906)   84220410 byte
pickle2                     4.623s     2.717s     2.093 (1.298,1.906)  138269939 byte
json_str                    5.036s     3.130s     2.411 (1.298,1.906)   84040832 byte
json_fh                     9.213s     7.307s     5.630 (1.298,1.906)   82992256 byte



# check which serializations are identical across python versions
{ { find -type f | while read fn; do [[ $(head -n 3 "$fn" | wc -c) -gt 300 ]] && { sha256sum "$fn"; continue; }; head -n 1 "$fn" | grep -qE '[^a-zA-Z][a-zA-Z]{8}[^a-zA-Z]' || { sha256sum "$fn"; continue; }; printf '%s %s\n' "$(sed -r 's/([^a-zA-Z])[a-zA-Z]{8}([^a-zA-Z])/\1\2/' < "$fn" | sha256sum)" "$fn"; done; sleep 1; echo; } | tee /dev/stderr; } | sort 



## TEST
with open('/dev/shm/py2.repr', 'rb') as f: eval(f.read().decode('utf-8'))
with open('/dev/shm/py3.repr', 'rb') as f: eval(f.read().decode('utf-8'))
with open('/dev/shm/py2.repr', 'rb') as f: __import__('json').dumps(eval(f.read().decode('utf-8')))
with open('/dev/shm/py3.repr', 'rb') as f: __import__('json').dumps(eval(f.read().decode('utf-8')))

## RESULT
Python 2.7.13 (default, Nov 24 2017, 17:33:09) Linux
Python 2.6 (r26:66721, Oct  2 2008, 11:35:03) Windows
[5, u'eyFEfvUb', u'\u591agt\u6d41LD GlONE\'r/u\u5b87FZX\u3057A\\iz  iKhz  ep"pOzwvA \\ah']
[5, 'RHrVSKcB', '\xe5\xa4\x9agt\xe6\xb5\x81LD GlONE\'r/u\xe5\xae\x87FZX\xe3\x81\x97A\\iz  iKhz  ep"pOzwvA \\ah']
'[5, "eyFEfvUb", "\\u591agt\\u6d41LD GlONE\'r/u\\u5b87FZX\\u3057A\\\\iz  iKhz  ep\\"pOzwvA \\\\ah"]'
'[5, "RHrVSKcB", "\\u591agt\\u6d41LD GlONE\'r/u\\u5b87FZX\\u3057A\\\\iz  iKhz  ep\\"pOzwvA \\\\ah"]'

## RESULT
Python 3.5.3 (default, Jan 19 2017, 14:11:04) Linux
Python 3.6.2 (v3.6.2:5fd33b5, Jul  8 2017, 04:57:36) Windows
[5, 'eyFEfvUb', '多gt流LD GlONE\'r/u宇FZXしA\\iz  iKhz  ep"pOzwvA \\ah']
[5, 'RHrVSKcB', '多gt流LD GlONE\'r/u宇FZXしA\\iz  iKhz  ep"pOzwvA \\ah']
'[5, "eyFEfvUb", "\\u591agt\\u6d41LD GlONE\'r/u\\u5b87FZX\\u3057A\\\\iz  iKhz  ep\\"pOzwvA \\\\ah"]'
'[5, "RHrVSKcB", "\\u591agt\\u6d41LD GlONE\'r/u\\u5b87FZX\\u3057A\\\\iz  iKhz  ep\\"pOzwvA \\\\ah"]'



## TEST
with open('/dev/shm/py2.repr', 'rb') as f: v2=eval(f.read().decode('utf-8'))[2]
with open('/dev/shm/py3.repr', 'rb') as f: v3=eval(f.read().decode('utf-8'))[2]
if v2==v3: print('eval(py2repr) == eval(py3repr)')

## py2 FAIL, fix:
if isinstance(v3,str): v3=v3.decode('utf-8')

## py3 SUCCESS



## TEST
with open('/dev/shm/py2.repr', 'rb') as f: v2=__import__('ast').literal_eval(f.read().decode('utf-8'))[2]
with open('/dev/shm/py3.repr', 'rb') as f: v3=__import__('ast').literal_eval(f.read().decode('utf-8'))[2]
if v2==v3: print('eval(py2repr) == eval(py3repr)')

# same results as with native eval


"""
