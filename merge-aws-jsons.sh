#!/usr/bin/env bash

# Finds all AWS json files in aws_configs folders, and merges them
# per region into a single aws_configs folder into the directory passed
# as argument (or `out_merged` as default).
#
# Needs: jq binary
#
# Useful to load a snapshot combined from multiple accounts into Batfish.

set -euo pipefail

OUT_DIR=${1:-out_merged}

REGIONS=$(find . -type d | sed -n  's/.*aws_configs\/\([^\/]*\).*/\1/; T; p' | sort -u)
JSONS_KINDS=$(find . -type f -regex ".*/aws_configs/.*\.json" | xargs -n1 basename | sort -u)

echo "Regions: ${REGIONS}"
echo "JSON kinds: ${JSONS_KINDS}"

#echo "==== Stats of resource counts"
#
#for f in $(find . -type f -name "*.json" | grep aws-snapshot)
#do
#    echo "File $f"
#    jq 'to_entries | group_by(.key) | map({k:.[0].key, cnt:map(.value | length)})' $f
#done

for r in $REGIONS
do
    OUT="${OUT_DIR}/aws_configs/${r}"
    mkdir -p "${OUT}"

    for j in $JSONS_KINDS
    do
      FILES=$(find . -type f -regex ".*${r}/${j}")
      echo "Merging ${j} in ${r}: ${FILES}"
      # Note: below will correctly merge json files with multiple keys at the top level, though in practice
      # if there was no "Marker" in the output due to paging, there will only be a single top-level key.
      jq -s '. |map(to_entries) | flatten(1) | group_by(.key) | map({key: .[0].key, value: map(.value) | add}) | from_entries' ${FILES} > "${OUT}/${j}"
    done
done
