# -*- coding: utf-8 -*-
from __future__ import print_function
from .__init__ import *
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

from .util import *



# copied from  http://xxyxyz.org/line-breaking/
#
# license clarified per email:
#   BSD or MIT since the EU doesn't recognize Public Domain
#
# only change so far is replacing len() with visual_length()
#
# select which unragger to use at the bottom of this file



def unrag_1_linear(text, width):
	words = text.split()
	count = len(words)
	offsets = [0]
	for w in words:
		offsets.append(offsets[-1] + visual_length(w))

	minima = [0] + [10 ** 20] * count
	breaks = [0] * (count + 1)

	def cost(i, j):
		w = offsets[j] - offsets[i] + j - i - 1
		if w > width:
			return 10 ** 10 * (w - width)
		return minima[i] + (width - w) ** 2

	def smawk(rows, columns):
		stack = []
		i = 0
		while i < len(rows):
			if stack:
				c = columns[len(stack) - 1]
				if cost(stack[-1], c) < cost(rows[i], c):
					if len(stack) < len(columns):
						stack.append(rows[i])
					i += 1
				else:
					stack.pop()
			else:
				stack.append(rows[i])
				i += 1
		rows = stack

		if len(columns) > 1:
			smawk(rows, columns[1::2])

		i = j = 0
		while j < len(columns):
			if j + 1 < len(columns):
				end = breaks[columns[j + 1]]
			else:
				end = rows[-1]
			c = cost(rows[i], columns[j])
			if c < minima[columns[j]]:
				minima[columns[j]] = c
				breaks[columns[j]] = rows[i]
			if rows[i] < end:
				i += 1
			else:
				j += 2

	n = count + 1
	i = 0
	offset = 0
	while True:
		r = min(n, 2 ** (i + 1))
		edge = 2 ** i + offset
		smawk(range(0 + offset, edge), range(edge, r + offset))
		x = minima[r - 1 + offset]
		for j in range(2 ** i, r - 1):
			y = cost(j + offset, r - 1 + offset)
			if y <= x:
				n -= j
				i = 0
				offset += j
				break
		else:
			if r == n:
				break
			i = i + 1

	lines = []
	j = count
	while j > 0:
		i = breaks[j]
		lines.append(u' '.join(words[i:j]))
		j = i
	lines.reverse()
	return lines



from collections import deque 

def unrag_2_binary(text, width):
    words = text.split()
    count = len(words)
    offsets = [0]
    for w in words:
        offsets.append(offsets[-1] + visual_length(w))

    minima = [0] * (count + 1)
    breaks = [0] * (count + 1)

    def c(i, j):
        w = offsets[j] - offsets[i] + j - i - 1
        if w > width:
            return 10 ** 10 * (w - width)
        return minima[i] + (width - w) ** 2

    def h(l, k):
        low, high = l + 1, count
        while low < high:
            mid = (low + high) // 2
            if c(l, mid) <= c(k, mid):
                high = mid
            else:
                low = mid + 1
        if c(l, high) <= c(k, high):
            return high
        return l + 2

    q = deque([(0, 1)])
    for j in range(1, count + 1):
        l = q[0][0]
        if c(j - 1, j) <= c(l, j):
            minima[j] = c(j - 1, j)
            breaks[j] = j - 1
            q.clear()
            q.append((j - 1, j + 1))
        else:
            minima[j] = c(l, j)
            breaks[j] = l
            while c(j - 1, q[-1][1]) <= c(q[-1][0], q[-1][1]):
                q.pop()
            q.append((j - 1, h(j - 1, q[-1][0])))
            if j + 1 == q[1][1]:
                q.popleft()
            else:
                q[0] = q[0][0], (q[0][1] + 1)

    lines = []
    j = count
    while j > 0:
        i = breaks[j]
        lines.append(u' '.join(words[i:j]))
        j = i
    lines.reverse()
    return lines



def unrag_3_divide(text, width):
    words = text.split()
    count = len(words)
    offsets = [0]
    for w in words:
        offsets.append(offsets[-1] + visual_length(w))

    minima = [0] + [10 ** 20] * count
    breaks = [0] * (count + 1)

    def cost(i, j):
        w = offsets[j] - offsets[i] + j - i - 1
        if w > width:
            return 10 ** 10
        return minima[i] + (width - w) ** 2

    def search(i0, j0, i1, j1):
        stack = [(i0, j0, i1, j1)]
        while stack:
            i0, j0, i1, j1 = stack.pop()
            if j0 < j1:
                j = (j0 + j1) // 2
                for i in range(i0, i1):
                    c = cost(i, j)
                    if c <= minima[j]:
                        minima[j] = c
                        breaks[j] = i
                stack.append((breaks[j], j+1, i1, j1))
                stack.append((i0, j0, breaks[j]+1, j))

    n = count + 1
    i = 0
    offset = 0
    while True:
        r = min(n, 2 ** (i + 1))
        edge = 2 ** i + offset
        search(0 + offset, edge, edge, r + offset)
        x = minima[r - 1 + offset]
        for j in range(2 ** i, r - 1):
            y = cost(j + offset, r - 1 + offset)
            if y <= x:
                n -= j
                i = 0
                offset += j
                break
        else:
            if r == n:
                break
            i = i + 1

    lines = []
    j = count
    while j > 0:
        i = breaks[j]
        lines.append(u' '.join(words[i:j]))
        j = i
    lines.reverse()
    return lines



def unrag_4_shortest(text, width):
    words = text.split()
    count = len(words)
    offsets = [0]
    for w in words:
        offsets.append(offsets[-1] + visual_length(w))

    minima = [0] + [10 ** 20] * count
    breaks = [0] * (count + 1)
    for i in range(count):
        j = i + 1
        while j <= count:
            w = offsets[j] - offsets[i] + j - i - 1
            if w > width:
                break
            cost = minima[i] + (width - w) ** 2
            if cost < minima[j]:
                minima[j] = cost
                breaks[j] = i
            j += 1

    lines = []
    j = count
    while j > 0:
        i = breaks[j]
        lines.append(u' '.join(words[i:j]))
        j = i
    lines.reverse()
    return lines



def bench_unrag(fname):
	t0 = time.time()
	n_lines = 0
	trend = {}
	with open(fname, 'rb') as f:
		for ln in f:
			n_lines += 1

	with open(fname, 'rb') as f:
		for n, ln in enumerate(f):
			if n % 8192 == 8191:
				t = time.time()
				print('{0:7} / {1}  {2:.3f}%  {3:.0f} p/s'.format(
					n, n_lines, n*100.0/n_lines, n/(t-t0)))
			ln = ln.decode('utf-8')
			if len(ln) < 40:
				ln = ln + ' ' + ln
			w = unrag(ln, 40)
			try:
				trend[len(w)] += 1
			except:
				trend[len(w)] = 1

	for k, v in sorted(trend.items()):
		print('{0} lines: {1} occurences'.format(k, v))

	t = time.time()
	print(n_lines)
	print(t-t0)



def unrag_layout_test_dump():
	scrw = 572
	msg = "012345678901234567890 Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
	msg = msg + ' ' + msg
	wrappers = [ unrag_1_linear, unrag_2_binary, unrag_3_divide, unrag_4_shortest ]
	avail = scrw/len(wrappers)
	last_txt = None
	for msgw in range(10, avail):
		print(msgw)
		results = []
		for wrapper in wrappers:
			results.append(wrapper(' '.join(prewrap(msg, msgw)), msgw))
			#results[-1].insert(0, '{0} {1}'.format(msgw, wrapper.__name__))
		txt = u''
		for row in range(0, 1000):
			ln = u'\n'
			for nr, result in enumerate(results):
				if len(result) <= row:
					ln += u' ' * avail
				else:
					ln += '\033[1;3{0}m{1}{2}\033[1;30m.{3}'.format(
						nr+1, result[row],
						u' ' * (msgw-len(result[row])),
						u' ' * (avail-msgw-1))
			if not ln.strip():
				break
			txt += '\033[G' + ln
		if txt != last_txt:
			print(txt)
		last_txt = txt



def unrag_layout_test_interactive():
	try: input = raw_input
	except NameError: pass

	try:
		import msvcrt
	except:
		import sys, tty, termios
	def getch():
		try:
			return msvcrt.getch()
		except:
			fd = sys.stdin.fileno()
			old_cfg = termios.tcgetattr(fd)
			tty.setraw(sys.stdin.fileno())
			ret = sys.stdin.read(1)
			termios.tcsetattr(fd, termios.TCSADRAIN, old_cfg)
			return ret
	
	msg = "012345678901234567890 Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
	msg = msg + ' ' + msg
	wrappers = [ unrag_1_linear, unrag_2_binary, unrag_3_divide, unrag_4_shortest ]
	iwrapper = 0
	msgw = 20
	while True:
		if msgw < 3:
			msgw = 3
		if iwrapper < 0:
			iwrapper = len(wrappers) - 1
		if iwrapper >= len(wrappers):
			iwrapper = 0

		pwrap = ' '.join(prewrap(msg, msgw))
		wraps = []
		uniq_wraps = []
		for wrapper in wrappers:
			wrap = '\n'.join(wrapper(pwrap, msgw))
			wraps.append(wrap)
			if wrap not in uniq_wraps:
				uniq_wraps.append(wrap)

		wrapped = wraps[iwrapper]
		print('{0}\033[H\033[J\n  {1} {2}  ~{3}\n\n{4}'.format(
			'\n'*20, msgw, wrappers[iwrapper].__name__, len(uniq_wraps), wrapped))

		ch = getch()
		if ch == b'\x03': sys.exit(0)
		elif ch == b'a': iwrapper -= 1
		elif ch == b'd': iwrapper += 1
		elif ch == b'w': msgw -= 1
		elif ch == b's': msgw += 1



unrag_bench_results = """
unrag_1_linear
   8191 / 853993  0.959%  4315 p/s
  16383 / 853993  1.918%  4643 p/s
  24575 / 853993  2.878%  4771 p/s
  32767 / 853993  3.837%  4767 p/s
  40959 / 853993  4.796%  4801 p/s
  49151 / 853993  5.755%  4803 p/s
  57343 / 853993  6.715%  4841 p/s
0 lines: 22 occurences
1 lines: 66708 occurences
2 lines: 508953 occurences
3 lines: 88698 occurences
4 lines: 104985 occurences
5 lines: 81862 occurences
6 lines: 2764 occurences
7 lines: 1 occurences
166.26898884773254

unrag_2_binary
   8191 / 853993  0.959%  4710 p/s
  16383 / 853993  1.918%  5103 p/s
  24575 / 853993  2.878%  5248 p/s
  32767 / 853993  3.837%  5253 p/s
  40959 / 853993  4.796%  5289 p/s
  49151 / 853993  5.755%  5292 p/s
  57343 / 853993  6.715%  5332 p/s
0 lines: 22 occurences
1 lines: 36691 occurences
2 lines: 508243 occurences
3 lines: 93677 occurences
4 lines: 124877 occurences
5 lines: 87375 occurences
6 lines: 2996 occurences
7 lines: 72 occurences
8 lines: 16 occurences
9 lines: 21 occurences
10 lines: 3 occurences
149.93761730194092

unrag_3_divide
   8191 / 853993  0.959%  6596 p/s
  16383 / 853993  1.918%  7298 p/s
  24575 / 853993  2.878%  7580 p/s
  32767 / 853993  3.837%  7627 p/s
  40959 / 853993  4.796%  7713 p/s
  49151 / 853993  5.755%  7749 p/s
  57343 / 853993  6.715%  7816 p/s
0 lines: 22 occurences
1 lines: 68011 occurences
2 lines: 512204 occurences
3 lines: 84440 occurences
4 lines: 104785 occurences
5 lines: 81780 occurences
6 lines: 2750 occurences
7 lines: 1 occurences
101.88200402259827

unrag_4_shortest
   8191 / 853993  0.959%  8149 p/s
  16383 / 853993  1.918%  9167 p/s
  24575 / 853993  2.878%  9563 p/s
  32767 / 853993  3.837%  9664 p/s
  40959 / 853993  4.796%  9649 p/s
  49151 / 853993  5.755%  9495 p/s
  57343 / 853993  6.715%  9448 p/s
0 lines: 22 occurences
1 lines: 85310 occurences
2 lines: 497438 occurences
3 lines: 82328 occurences
4 lines: 104426 occurences
5 lines: 81719 occurences
6 lines: 2749 occurences
7 lines: 1 occurences
82.48605155944824
"""



# divide and shortest are the most A E S T H E T I C
# shortest wins just barely

#unrag = unrag_1_linear    # 166sec
#unrag = unrag_2_binary    # 150sec
#unrag = unrag_3_divide    # 102sec
unrag = unrag_4_shortest   #  82sec
