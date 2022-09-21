#!/usr/bin/env bash

# Finds all AWS json files in aws_configs folders, and merges them
# per region into a single aws_configs folder in 'out-merged' dir.
#
# Useful to load a snapshot combined from multiple accounts into Batfish.

set -euo pipefail

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
    OUT="out-merged/aws_configs/${r}"
    mkdir -p "${OUT}"

    for j in $JSONS_KINDS
    do
      FILES=$(find . -type f -regex ".*${r}/${j}")
      echo "Merging ${j} in ${r}: ${FILES}"
      jq -s '. |map(to_entries) | flatten(1) | group_by(.key) | map({key: .[0].key, value: map(.value) | add}) | from_entries' ${FILES} > "${OUT}/${j}"
    done
done
