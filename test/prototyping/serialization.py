#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function


import os
import sys
import time
import random
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


def result(desc, sec, fn=None):
	if fn:
		print(u'{0:14} {1:11.3f}s   {2:9} byte'.format(
			desc, sec, os.path.getsize(fn)))
	else:
		print(u'{0:14} {1:11.3f}s'.format(desc, sec))


def gen_sentence():
	letters = u'宇多田ヒカル桜流しABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz        '
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


if not os.path.isfile('txt'):
	t0 = time.time()
	with open('txt', 'wb') as f:
		for n in range(1048576):
			if n % 8192 == 0:
				print('{0}  {1:.2f}%'.format(n, n*100.0/1048576))
			f.write(u'{0}\n'.format(gen_sentence()).encode('utf-8'))
	result('gen lines', time.time()-t0)


def stream_txt():
	with open('txt', 'rb') as f:
		for ln in f:
			yield ln.decode('utf-8').rstrip()


def stream_msgs():
	iuser = 0
	with open('txt', 'rb') as f:
		for n, ln in enumerate(f):
			txt = ln.decode('utf-8').rstrip()
			if n % 32 == 31:
				mid = int(len(txt) / 2)
				txt = u'{0}\n{1}'.format(txt[:mid], txt[mid:])

			yield Message(users[iuser], n, txt)
			iuser += 1
			if iuser >= len(users):
				iuser = 0


for run in range(2):
	t0 = time.time()
	for ln in stream_txt():
		pass
	result('stream utf8', time.time()-t0, 'txt')


for run in range(2):
	t0 = time.time()
	for msg in stream_msgs():
		pass
	result('stream msgs', time.time()-t0)


if True:

	for run in range(2):
		t0 = time.time()
		with open('txt_srpl', 'wb') as f:
			for msg in stream_msgs():
				f.write(u'{0} {1} {2}\n'.format(
					msg.ts, msg.user, msg.txt.replace(u'a', u'\\a')).\
					encode('utf-8'))
		result('write txt_srpl', time.time()-t0, 'txt_srpl')


	for run in range(2):
		t0 = time.time()
		with open('txt_repr', 'wb') as f:
			for msg in stream_msgs():
				f.write(repr(u'{0} {1} {2}\n'.format(
					msg.ts, msg.user, repr(msg.txt))).\
					encode('utf-8'))
		result('write txt_repr', time.time()-t0, 'txt_repr')


for run in range(2):
	t0 = time.time()
	with open('lst_repr', 'wb') as f:
		for msg in stream_msgs():
			f.write(u'{0}\n'.format(
				repr([msg.ts, msg.user, msg.txt])).\
				encode('utf-8'))
	result('write lst_repr', time.time()-t0, 'lst_repr')


	#for run in range(2):
	#	t0 = time.time()
	#	with open('msg_repr', 'wb') as f:
	#		for msg in stream_msgs():
	#			f.write(u'{0}\n'.format(
	#				repr(msg)).\
	#				encode('utf-8'))
	#	result('write msg_repr', time.time()-t0, 'msg_repr')


if True:

	for run in range(2):
		t0 = time.time()
		with open('uesc', 'wb') as f:
			for msg in stream_msgs():
				f.write(u'{0}\n'.format(
					u'{0} {1} {2}'.format(
						msg.ts, msg.user, msg.txt).\
						encode('unicode_escape')).\
					encode('utf-8'))
		result('write uesc', time.time()-t0, 'uesc')


	for run in range(2):
		t0 = time.time()
		with open('p2', 'wb') as f:
			for msg in stream_msgs():
				pickle.dump(msg, f, 2)
		result('write cPickle2', time.time()-t0, 'p2')


	for run in range(2):
		t0 = time.time()
		with open('json', 'wb') as f:
			for msg in stream_msgs():
				f.write(json.dumps([msg.ts, msg.user, msg.txt]).encode('utf-8'))
		result('write json.str', time.time()-t0, 'json')


	for run in range(2):
		t0 = time.time()
		with open('json', 'w') as f:
			for msg in stream_msgs():
				json.dump([msg.ts, msg.user, msg.txt], f)
		result('write json.fh', time.time()-t0, 'json')


"""
RESULTS // py3.6.2 // win64 
stream utf8       0.830s    45726059 byte
stream msgs       1.733s
write txt_srpl    4.408s    62956241 byte
write txt_repr    5.172s    67683621 byte
write lst_repr    4.983s    70829349 byte
write uesc        6.293s    84194077 byte
write cPickle2    9.151s   138917995 byte
write json.str    8.536s    83736479 byte
write json.fh    19.077s    83736479 byte

RESULTS // py2.6.0 // win64 
stream utf8       1.422s    45726059 byte
stream msgs       2.268s
write txt_srpl    5.952s    62956241 byte
write txt_repr    8.575s    88388381 byte
write lst_repr    7.434s    86882207 byte
write msg_repr    5.817s    41943040 byte  lol
write uesc        8.125s    76396447 byte
write cPickle2   13.066s   129480587 byte
write json.str   15.579s    83736479 byte
write json.fh    14.837s    83736479 byte
"""
