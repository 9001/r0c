#!/bin/bash
set -e

w=$(tput cols)
[ $w -gt 48 ] ||
{
	echo "screen 2 smol"
	exit 1
}

[ -e r0c/__main__.py ] || cd ..
[ -e r0c/__main__.py ] || cd ~/dev/r0c
[ -e r0c/__main__.py ] || exit 1
cd log/wire

while read ts ip port
do
	printf '\033[36m%19s \033[33m%-15s \033[1;30m%-5s\033[0m  ' \
		"$(date +'%Y-%m-%d %H:%M:%S' --date=@$ts)" "$ip" "$port"
	
	cat -- "${ts}_${ip}_${port}" |
	grep -E '^> .. .. .. .. ' |
	sed -r '
		# wire log v1
		s/> ..           (.) $/\1/;
		s/> .. ..        (..) $/\1/;
		s/> .. .. ..     (...) $/\1/;
		s/> .. .. .. ..  (....) $/\1/;
		# wire log v2
		s/> ..          (.)$/\1/;
		s/> .. ..       (..)$/\1/;
		s/> .. .. ..    (...)$/\1/;
		s/> .. .. .. .. (....)$/\1/' |

	tr -d '\n' |
	awk '
		BEGIN {
			wi = '$((w-44))'
			wc = 43
			w  = wi
		}

		{
			while (length > w) {
				print substr($0, 1, w)
				$0 = sprintf("%" wc "s%s", "", substr($0, w + 1))
				w = wi + wc
			}
			print
		}
	'
	echo
done < <(
	find -maxdepth 1 |
	grep -E '^..[0-9]{6,12}_[0-9]{1,3}\.' |
	sed -r 's/..//;s/_/ /;s/_/ /' |
	sort -n
) |
grep -vE '^$'

