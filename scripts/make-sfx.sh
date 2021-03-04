#!/bin/bash
set -e
echo


# optional args:
#
# `clean` uses files from git (everything except web/deps),
#   so local changes won't affect the produced sfx


# differences from copyparty sfx:
# - no jinja stuff
# - no python scanning stuff
# - no unexpand (breaks heredoc)
# - but does share/docs instead
# - site-packages subfolder


name=r0c

[ -e $name/__main__.py ] || cd ..
[ -e $name/__main__.py ] ||
{
	printf "run me from within the project root folder\n\n"
	exit 1
}

resources=(
	docs/*.md
	clients
)

command -v gtar  >/dev/null &&
command -v gfind >/dev/null && {
	tar()  { gtar  "$@"; }
	sed()  { gsed  "$@"; }
	find() { gfind "$@"; }
	sort() { gsort "$@"; }
}

while [ ! -z "$1" ]; do
	[ "$1" = clean  ] && clean=1  && shift && continue
	break
done

tmv() {
	touch -r "$1" t
	mv t "$1"
}

rm -rf sfx/*
mkdir -p sfx build
cd sfx

# msys2 tar is bad, make the best of it
echo collecting source
[ $clean ] && {
	(cd .. && git archive master >tar) && tar -xf ../tar $name "${resources[@]}"
}
[ $clean ] || {
	(cd .. && tar -cf tar $name "${resources[@]}") && tar -xf ../tar
}
rm -f ../tar

ver=
git describe --tags >/dev/null 2>/dev/null && {
	git_ver="$(git describe --tags)";  # v0.5.5-2-gb164aa0
	ver="$(printf '%s\n' "$git_ver" | sed -r 's/^v//; s/-g?/./g')";
	t_ver=

	printf '%s\n' "$git_ver" | grep -qE '^v[0-9\.]+$' && {
		# short format (exact version number)
		t_ver="$(printf '%s\n' "$ver" | sed -r 's/\./, /g')";
	}

	printf '%s\n' "$git_ver" | grep -qE '^v[0-9\.]+-[0-9]+-g[0-9a-f]+$' && {
		# long format (unreleased commit)
		t_ver="$(printf '%s\n' "$ver" | sed -r 's/\./, /g; s/(.*) (.*)/\1 "\2"/')"
	}

	[ -z "$t_ver" ] && {
		printf 'unexpected git version format: [%s]\n' "$git_ver"
		exit 1
	}

	dt="$(git log -1 --format=%cd --date=short | sed -E 's/-0?/, /g')"
	printf 'git %3s: \033[36m%s\033[0m\n' ver "$ver" dt "$dt"
	sed -ri '
		s/^(VERSION =)(.*)/#\1\2\n\1 ('"$t_ver"')/;
		s/^(S_VERSION =)(.*)/#\1\2\n\1 "'"$ver"'"/;
		s/^(BUILD_DT =)(.*)/#\1\2\n\1 ('"$dt"')/;
	' $name/__version__.py
}

[ -z "$ver" ] && 
	ver="$(awk '/^VERSION *= \(/ {
		gsub(/[^0-9,]/,""); gsub(/,/,"."); print; exit}' < $name/__version__.py)"

ts=$(date -u +%s)
hts=$(date -u +%Y-%m%d-%H%M%S) # --date=@$ts (thx osx)

mkdir -p ../dist
sfx_out=../dist/$name

echo cleanup
find .. -name '*.pyc' -delete
find .. -name __pycache__ -delete

# especially prevent osx from leaking your lan ip (wtf apple)
find .. -type f \( -name .DS_Store -or -name ._.DS_Store \) -delete
find .. -type f -name ._\* | while IFS= read -r f; do cmp <(printf '\x00\x05\x16') <(head -c 3 -- "$f") && rm -f -- "$f"; done

# disable password check (TODO should be a r0c option probably)
f=$name/__main__.py
awk '/change the ADMIN_PWD/{o=1} o&&/return False$/{sub(/False/,"True");o=0} 1' <$f >t
tmv "$f"

# cleanup junk
find . -type f |
grep -vE '\.(md|py)$|clients/' |
tr '\n' '\0' |
xargs -0r rm --

# r0c needs the docs here
rm -f docs/todo.md
mkdir -p share/doc/r0c/
mv docs share/doc/r0c/help
mkdir site-packages
mv $name share site-packages

echo
echo creating tar
args=(--owner=1000 --group=1000)
[ "$OSTYPE" = msys ] &&
	args=()

(for d in clients site-packages; do
	find $d -type f;
done) |
LC_ALL=C sort |
tar -cvf tar "${args[@]}" --numeric-owner -T-

echo
echo compressing tar
# detect best level; bzip2 -7 is usually better than -9
for n in {2..9}; do cp tar t.$n; bzip2 -$n t.$n & done; wait; mv -v $(ls -1S t.*.bz2 | tail -n 1) tar.bz2
rm t.*

echo creating sfx
python ../scripts/sfx.py --sfx-make tar.bz2 r0c $ver $ts
mv sfx.out $sfx_out.py
chmod 755 $sfx_out.*

printf "done:\n"
printf "  %s\n" "$(realpath $sfx_out)."py
# rm -rf *

# tar -tvf ../sfx/tar | sed -r 's/(.* ....-..-.. ..:.. )(.*)/\2 `` \1/' | sort | sed -r 's/(.*) `` (.*)/\2 \1/'| less
# for n in {1..9}; do tar -tf tar | grep -vE '/$' | sed -r 's/(.*)\.(.*)/\2.\1/' | sort | sed -r 's/([^\.]+)\.(.*)/\2.\1/' | tar -cT- | bzip2 -c$n | wc -c; done 
