#!/usr/bin/env python3

import sys

PY2 = sys.version_info < (3,)

from corrupy import minimize

def main():
    if len(sys.argv) < 2:
        raise ValueError("No command line arguments given. Expected one or more filenames")

    for filename in sys.argv[1:]:
        print("minimizing {}".format(filename))

        if PY2:
            with open(filename, "rb") as f:
                data = f.read()
        else:
            with open(filename, "r", encoding="utf-8") as f:
                data = f.read()

        output = minimize.minimize(
            data,
            remove_docs=True, obfuscate_globals=False,
            obfuscate_builtins=False, obfuscate_imports=False
        )

        if PY2:
            with open(filename, "wb") as f:
                f.write(output)
        else:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(output)

if __name__ == '__main__':
    main()
