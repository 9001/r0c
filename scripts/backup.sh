#!/bin/bash
set -e

mkdir ~/dev/backups; cd ~/dev && tar -czvf backups/r0c-$(date +%Y-%m%d-%H%M).tgz --exclude='*.pyc' r0c 

