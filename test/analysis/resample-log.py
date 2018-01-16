#!/usr/bin/env python2
from __future__ import print_function

NUM_INPUT_COLS = 4

import re
import sys

if len(sys.argv) < 2:
	print('need argument 1:  graph to resample+derive')
	sys.exit(1)

fn = sys.argv[1]

# 1516048842.772  j 3324  p 3301  m 220488  d 168,167,9966
fmt_in = re.compile(r'^([0-9\.]+)  j ([0-9]+)  p ([0-9]+)  m ([0-9]+)  d ([0-9]+),([0-9]+),([0-9]+)$')

rows = []
with open(fn, 'rb') as f:
	for ln in f:
		m = fmt_in.match(ln.decode('utf-8').strip())
		if not m:
			continue
		rows.append([float(x) for x in m.groups()])

def resample(rows):
	ret = []
	for r2, r in zip(rows[:-1], rows[1:]):
		
		r2 = r2[:NUM_INPUT_COLS]
		r  =  r[:NUM_INPUT_COLS]
		
		# difference between r2 and r
		rd = []
		for v2, v in zip(r2, r):
			rd.append(v-v2)
		
		# extract timestamp
		ts2 = r2[0]
		ts  =  r[0]
		
		its2 = int(ts2)
		its  = int(ts)
		
		# skip row if timestamp floors to the same
		if its2 == its:
			continue
		
		# all whole seconds between r2 and r
		for isec in range(its2+1, its+1):
			#print()
			#print('r2: ' + ''.join('{0}  '.format(x) for x in r2))
			#print('r:  ' + ''.join('{0}  '.format(x) for x in r))
			#print('rd: ' + ''.join('{0}  '.format(x) for x in rd))
			#print('isec {0}  [{1}..{2}]'.format(isec, its2+1, its+1))
			row = []
			mul = (isec * 1.0 - ts2) / (ts * 1.0 - ts2)
			for n, rv in enumerate(r):
				row.append(r2[n] + (rv-r2[n]) * mul)
			
			#print('ri: ' + ''.join('{0}  '.format(x) for x in row))
			ret.append(row)
	
	return ret


def derivate(rows):
	ret = []
	for r2, r in zip(rows[:-1], rows[1:]):
		rd = [r2[0]]
		for v2, v in zip(r2[1:], r[1:]):
			rd.append(v-v2)
		ret.append(rd)
	return ret


rows = resample(rows)
rows = derivate(rows)

# start counting time from 0
epoch = round(rows[0][0])
for n in range(len(rows)):
	rows[n][0] = int(round(rows[n][0]) - epoch)

for row in rows:
	print('{0}  {1:8.2f}  {2:8.2f}  {3:8.2f}'.format(*row))
