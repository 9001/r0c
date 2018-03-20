# -*- coding: utf-8 -*-
from __future__ import print_function
from .__init__ import *
if __name__ == '__main__':
  raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

import gc

# make everything familiar to globals()
from .config  import *
from .util    import *
from .unrag   import *
from .ivt100  import *
from .inetcat import *
from .itelnet import *
from .chat    import *
from .user    import *
from .world   import *

if PY2:
  from Queue import Queue
else:
  from queue import Queue



def memory_dump():
	import gc
	import _pickle as cPickle
	with open("profiler-results.memory", 'wb') as dump:
		for obj in gc.get_objects():
			i = id(obj)
			size = sys.getsizeof(obj, 0)
			#    referrers = [id(o) for o in gc.get_referrers(obj) if hasattr(o, '__class__')]
			referents = [id(o) for o in gc.get_referents(obj) if hasattr(o, '__class__')]
			if hasattr(obj, '__class__'):
				cls = str(obj.__class__)
				cPickle.dump({'id': i, 'class': cls, 'size': size, 'referents': referents}, dump)



def get_obj_name(target_id):
	variables = {**locals(), **globals()}
	for var in variables:
		exec('var_id=id({0})'.format(var))
		if var_id == target_id:
			exec('found={0}'.format(var))
	if found:
		print(found)
		print(id(found))
	else:
		print('/')

def find_leaked_messages():
	n_hits = 0
	for obj in gc.get_objects():
		if not type(obj) is Message:
			continue
		n_hits += 1
		if n_hits > 1000:
			break
		
		ref_objs = gc.get_referents(obj)
		referents = [id(o) for o in ref_objs if hasattr(o, '__class__')]
		print('obj,ref:',id(obj),referents)
		print('obj:',obj)
		print('ref:',ref_objs)
		print()

repl_notepad = """

from .diag import *
find_leaked_messages()

n_hits = 0
for obj in gc.get_objects():
  if not hasattr(obj, '__class__'):
    continue
  if type(obj) is Message:
    n_hits += 1
    if n_hits > 10000:
      break
    i = id(obj)
    size = sys.getsizeof(obj, 0)
    name = obj.__name__ if hasattr(obj, '__name__') else '/'
    referents = [id(o) for o in gc.get_referents(obj) if hasattr(o, '__class__')]
    print('id: {0}, size: {1}, class: {2}, name: {3}, referents: {4}'.format(
      i, size, str(obj.__class__), name, ', '.join([str(x) for x in referents])))

"""





# dumping ground for mostly useless code below

def test_ansi_annotation():
	rangetype = range
	try: rangetype = xrange
	except: pass
	ansi_txt = '\033[1;33mHello \033[1;32mWorld\033[0m! This \033[7mis\033[0m a test.\033[A'
	ansi_txt = '\033[mf\033[s\033[w\033[has\033[3451431613gt\033[m \033[s\033[g\033[s\033[g\033[s\033[gcod\033[me\033[x'
	rv = visual_indices(ansi_txt)
	print(' '.join(ansi_txt.replace('\033', '*')))
	print(' '.join([str(x%10) for x in rangetype(len(ansi_txt))]))
	print(' '.join([str(x) for x in rv]))
	print('{0} {1}'.format(visual_length(ansi_txt), len(rv)))
	visual = ''
	for ofs in rv:
		visual += ansi_txt[ofs]
	print('[{0}]'.format(visual))

	for outer_n in rangetype(3):

		t0 = time.time()
		for n in rangetype(100000):
			rv = visual_indices(ansi_txt)
		print(str(time.time() - t0))
		
		t0 = time.time()
		for n in rangetype(100000):
			rv = visual_length(ansi_txt)
		print(str(time.time() - t0))

