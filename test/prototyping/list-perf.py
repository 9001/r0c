#!/usr/bin/env python2

import time

t0 = 0


def td(msg):
    global t0
    t1 = time.time()
    print("{0}  {1:.6f}  {2}\n".format(t1, t1 - t0, msg))
    t0 = t1


class Foo(object):
    def __init__(self, n):
        self.n = n
        self.v2 = int(n * 1.3)


td("started")

n_mb = 24

haystack = []
needle = None
needle_at = int(n_mb * 1024 * 1024 * 0.74)
for n1 in range(n_mb):
    print(n_mb, n1)
    for n2 in range(1024):
        for n3 in range(1024):
            n = (n1 * 1024 + n2) * 1024 + n3
            haystack.append(Foo(n))
            if n == needle_at:
                needle = haystack[-1]
td("built list")

# print(haystack.index(needle))
# td('find needle')
print(haystack[needle_at])
td("get abs pos needle")

print(haystack[int(0.31 * n_mb * 1024 * 1024)])
td("get abs pos other")

# py2 58.6% ram
# 1515537393.86  25.088947  built list
# 1515537394.18   0.313340  find needle
# 1515537394.18   0.000040  get abs pos

# py3 31.7% ram
# 1515537445.5261745  21.067613  built list
# 1515537445.7479792   0.221805  find needle
# 1515537445.7480137   0.000035  get abs pos

# ^ without v2 member
# |
# v with v2 member

# py2 62.3% ram
# 1515537643.67  29.696990  built list
# 1515537643.67  0.000044  get abs pos needle
# 1515537643.67  0.000017  get abs pos other

# py3 36.5% ram
# 1515537590.0602984  27.699614  built list
# 1515537590.0603702  0.000072  get abs pos needle
# 1515537590.060382  0.000012  get abs pos other
