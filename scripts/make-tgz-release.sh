#!/bin/bash
set -e
echo

sed=$( which gsed  2>/dev/null || which sed)
find=$(which gfind 2>/dev/null || which find)
sort=$(which gsort 2>/dev/null || which sort)

which md5sum 2>/dev/null >/dev/null &&
	md5sum=md5sum ||
	md5sum="md5 -r"

ver="$1"

[ "x$ver" == x ] &&
{
	echo "need argument 1:  version"
	echo
	exit 1
}

[ -e r0c/__main__.py ] || cd ..
[ -e r0c/__main__.py ] ||
{
	echo "run me from within the r0c folder"
	echo
	exit 1
}

out_dir="$(pwd | $sed -r 's@/[^/]+$@@')"
zip_path="$out_dir/r0c-$ver.zip"
tgz_path="$out_dir/r0c-$ver.tar.gz"

[ -e "$zip_path" ] ||
[ -e "$tgz_path" ] &&
{
	echo "found existing archives for this version"
	echo "  $zip_path"
	echo "  $tgz_path"
	echo
	echo "continue?"
	read -u1
}
rm "$zip_path" 2>/dev/null || true
rm "$tgz_path" 2>/dev/null || true

#$sed -ri "s/^(ADMIN_PWD *= *u).*/\1'hunter2'/" r0c/config.py

tmp="$(mktemp -d)"
rls_dir="$tmp/r0c-$ver"
mkdir "$rls_dir"

echo ">>> export"
git archive master |
tar -x -C "$rls_dir"

cd "$rls_dir"
$find -type d -exec chmod 755 '{}' \+
$find -type f -exec chmod 644 '{}' \+

grep -qE "ADMIN_PWD *= *u'hunter2'" r0c/config.py ||
{
	echo "password not hunter2"
	rm -rf "$tmp"
	exit 1
}

commaver="$(
	printf '%s\n' "$ver" |
	sed -r 's/\./,/g'
)"

grep -qE "^VERSION *= \(${commaver}\)$" r0c/__version__.py ||
{
	echo "$tmp"
	echo "bad version"
	echo
	echo " arg: $commaver"
	echo "code: $(
		cat r0c/__version__.py |
		grep -E '^VERSION'
	)"
	echo
	echo "continue?"
	read -u1
}

rm \
  r0c.sublime-project \
  .editorconfig \
  .gitattributes \
  .gitignore

mv LICENSE LICENSE.txt

chmod 755 \
  start-r0c.sh \
  clients/bash.sh \
  scripts/py.sh \
  scripts/format-wire-logs.sh \
  test/run-stress.sh

$find -type f -exec $md5sum '{}' \+ |
$sed -r 's/(.{32})(.*)/\2\1/' | LC_COLLATE=c $sort |
$sed -r 's/(.*)(.{32})/\2\1/' |
$sed -r 's/^(.{32}) \./\1  ./' > ../.sums.md5
mv ../.sums.md5 .

cd ..
echo ">>> tar"; tar -czf "$tgz_path" "r0c-$ver"
echo ">>> zip"; zip -qr  "$zip_path" "r0c-$ver"

rm -rf "$tmp"
echo
echo "done:"
echo "  $zip_path"
echo "  $tgz_path"
echo

# function alr() { ls -alR r0c-$1 | $sed -r "s/r0c-$1/r0c/" | $sed -r 's/[A-Z][a-z]{2} [0-9 ]{2} [0-9]{2}:[0-9]{2}//' > $1; }; for x in master rls src ; do alr $x; done

