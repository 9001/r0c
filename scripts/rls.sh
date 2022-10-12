#!/bin/bash
set -e

[ -e make-sfx.sh ] || cd scripts
[ -e make-sfx.sh ] || {
    echo cd into the scripts folder first
    exit 1
}

v=$1

[ "$v" = sfx ] || {
    printf '%s\n' "$v" | grep -qE '^[0-9\.]+$' || exit 1
    grep -E "(${v//./, })" ../r0c/__version__.py || exit 1

    git tag v$v
    git push --all
    git push --tags
    ./make-pypi-release.sh u
    ./make-tgz-release.sh $v
}

f=~/dev/r0c/dist/r0c.py
min=999999
while true; do
    ./make-sfx.sh
    s=$(stat -c%s $f)
    [ $s -lt $min ] ||
        continue
    
    mv $f $f.$s
    min=$s
done
