# test case for multithreaded access to the print() builtin,
# the native print appears to have a mutex covering the main message
# but the 'end' variable is tacked on outside of it
# meaning you might lose the newline to a pending message

with open('string-encoding.txt', 'rb') as f:
	text = f.read().decode('utf-8')


# nice: wraps everything in ' then escapes ' to \'
#       converts newline to \n
#       keeps moonrunes as-is
with open('tmp.string-encoding.repr', 'wb') as f:
	f.write(repr(text).encode('utf-8'))


# meh: converts newline to \n
#      converts moonrunes to \uC0DE
with open('tmp.string-encoding.unicode_escape', 'wb') as f:
	f.write(text.encode('unicode_escape'))


# useless:  keeps newlines as \x0a
#           converts moonrunes to \uC0DE
with open('tmp.string-encoding.raw_unicode_escape', 'wb') as f:
	f.write(text.encode('raw_unicode_escape'))


# useless:  it does nothing
with open('tmp.string-encoding.unicode_internal', 'wb') as f:
	f.write(text.encode('unicode_internal'))


try:
	with open('tmp.string-encoding.string_escape', 'wb') as f:
		f.write(text.encode('string_escape'))
except:
	print('err string_escape')

