"""
Karen's Ear — Link Verification Tool: CrisiText Dataset Handshake
Verifies access to LanD-FBK/crisitext on Hugging Face without downloading the entire dataset.
Inspects metadata, splits, column schema, and streams a minimal sample.
"""

import sys
import time

DATASET_NAME = "LanD-FBK/crisitext"


def main() -> int:
    print("\n--- [CHECK: CrisiText Dataset Access] ---")
    start_time = time.time()
    try:
        from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset
    except ImportError as e:
        print(f"  [FAIL] Hugging Face datasets library not installed: {e}")
        print(">>> RESULT: [FAIL]")
        return 1

    try:
        print(f"  Connecting to Hugging Face Hub for: {DATASET_NAME}")
        splits = get_dataset_split_names(DATASET_NAME)
        print(f"  Available Splits: {splits}")

        # Stream only 1 sample record to avoid heavy downloading
        print("  Streaming 1 sample record from 'train' split...")
        ds_stream = load_dataset(DATASET_NAME, split="train", streaming=True)
        sample = next(iter(ds_stream))

        elapsed = round(time.time() - start_time, 2)
        columns = list(sample.keys())
        print(f"  Columns Verified ({len(columns)}): {columns}")
        print(f"  Sample ID: {sample.get('scenario_id')}")
        print(f"  Sample Source: {sample.get('source')}")
        desc_preview = str(sample.get('original_description', ''))[:90]
        print(f"  Sample Description Preview: \"{desc_preview}...\"")
        print(f"  Handshake Latency: {elapsed}s")
        print(">>> RESULT: [PASS]")
        return 0

    except Exception as e:
        print(f"  [FAIL] CrisiText connection error: {e}")
        print(">>> RESULT: [FAIL]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
