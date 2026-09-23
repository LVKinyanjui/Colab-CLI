#!/bin/bash
while read -r url; do wget -c "$url"; done < blend_urls.txt
