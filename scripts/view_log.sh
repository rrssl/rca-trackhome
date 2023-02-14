#!/usr/bin/bash
awk -F"," '{OFS=","; $2=strftime("%Y-%m-%d %H:%M:%S", $2); print $0}' "$1" | column -s, -t | less
