VERSION = (1, 6, 0)
BUILD_DT = (2024, 4, 4)

S_VERSION = u".".join(map(str, VERSION))
S_BUILD_DT = u"{0:04d}-{1:02d}-{2:02d}".format(*BUILD_DT)

__version__ = S_VERSION
__build_dt__ = S_BUILD_DT

# I'm all ears
