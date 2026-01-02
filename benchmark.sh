#!/bin/bash

HDD_PATH="/storage/data1/zhangzeao/数据导出/"
SSD_PATH="/home/zhangzeao/Darcy/bone-kit/raw_images"

DENSE_FILTER=""
SPARSE_FILTER="--blacklist *.png --blacklist *.jpg"

BACKENDS=("rust" "python")
THREAD_COUNTS=(1 2 4 8 16 32)
SHUFFLE_MODES=("false" "true")
STORAGE_TYPES=("SSD" "HDD")
DENSITY_TYPES=("Dense" "Sparse")

DURATION=10
OUTPUT_FILE="benchmark_final.csv"

echo "Storage,Density,Backend,Threads,Order,MB/s,Files/s" >"$OUTPUT_FILE"

for storage in "${STORAGE_TYPES[@]}"; do
	[[ "$storage" == "SSD" ]] && CURRENT_PATH="$SSD_PATH" || CURRENT_PATH="$HDD_PATH"

	for density in "${DENSITY_TYPES[@]}"; do
		[[ "$density" == "Dense" ]] && CURRENT_FILTER="$DENSE_FILTER" || CURRENT_FILTER="$SPARSE_FILTER"

		for backend in "${BACKENDS[@]}"; do
			for shuffle in "${SHUFFLE_MODES[@]}"; do
				for threads in "${THREAD_COUNTS[@]}"; do

					echo ">>> [ $storage | $density ] Backend: $backend, Threads: $threads, Shuffle: $shuffle"

					echo "--- Cooling down & Syncing ---"
					sync
					sleep 1
					echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null
					sleep 1

					CMD_ARGS="\"$CURRENT_PATH\" --backend $backend --threads $threads --duration $DURATION $CURRENT_FILTER"
					[[ "$shuffle" == "true" ]] && CMD_ARGS="$CMD_ARGS --shuffle-files"

					OUTPUT=$(eval python benchmark.py "$CMD_ARGS" | grep "^RESULT|")

					if [[ -n "$OUTPUT" ]]; then
						CLEAN_DATA=$(echo "${OUTPUT#RESULT|}" | tr '|' ',')
						echo "$storage,$density,$CLEAN_DATA" >>"$OUTPUT_FILE"
						echo "    OK: $CLEAN_DATA"
					else
						echo "    FAILED: Program exited without RESULT line"
					fi

					sleep 0.5
				done
			done
		done
	done
done

echo -e "\nBenchmark Complete!"
column -s, -t <"$OUTPUT_FILE"
