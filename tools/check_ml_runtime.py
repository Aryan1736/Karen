"""
Karen's Ear — Link Verification Tool: ML Runtime Handshake
Verifies Hugging Face model loading and measures local CPU inference performance.
Evaluates sentence-transformers/all-MiniLM-L6-v2.
"""

import sys
import time

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TEST_SENTENCE = "Flash flood warning issued for northern district. Roads inundated and multiple vehicles stranded."


def main() -> int:
    print("\n--- [CHECK: ML Runtime Handshake] ---")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"  [FAIL] sentence-transformers library not installed: {e}")
        print(">>> RESULT: [FAIL]")
        return 1

    try:
        print(f"  Loading model: {MODEL_NAME}...")
        load_start = time.time()
        model = SentenceTransformer(MODEL_NAME, device="cpu")
        load_time = round((time.time() - load_start) * 1000, 2)
        print(f"  Model Loaded Successfully in {load_time} ms")

        # Warm-up inference
        _ = model.encode(["warm up test sentence"], device="cpu")

        # Measured sample inference
        print(f"  Executing test inference on sample emergency text...")
        inf_start = time.time()
        embedding = model.encode([TEST_SENTENCE], device="cpu")[0]
        inf_time = round((time.time() - inf_start) * 1000, 2)

        dim = len(embedding)
        norm = round(float((embedding ** 2).sum() ** 0.5), 4)

        print(f"  Inference Succeeded: True")
        print(f"  Embedding Dimension: {dim}")
        print(f"  Vector L2 Norm: {norm}")
        print(f"  Measured Local Inference Latency: {inf_time} ms (CPU)")
        print(">>> RESULT: [PASS]")
        return 0

    except Exception as e:
        print(f"  [FAIL] ML Runtime error: {e}")
        print(">>> RESULT: [FAIL]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
