"""Model pre-download and verification script for Laya weights."""

from __future__ import annotations

import argparse
import sys
import time

from finlaya.laya.model import LayaDecisionModel


def download_and_verify(model_id: str = "convaiinnovations/laya", device: str = "auto") -> bool:
    print("=" * 60)
    print(f"Laya Model Download & Local Cache Verification: {model_id}")
    print("=" * 60)

    print("Initializing model loader...")
    t0 = time.perf_counter()
    model = LayaDecisionModel(model_id=model_id, device=device)

    try:
        print(f"Downloading/loading weights for '{model_id}'...")
        model.load()
        load_time = time.perf_counter() - t0
        print(f"[PASS] Model successfully loaded in {load_time:.2f} seconds.")

        print("Executing test health-check inference...")
        t1 = time.perf_counter()
        passed = model.health_check()
        infer_time = time.perf_counter() - t1

        if passed:
            print(f"[PASS] Health check inference passed in {infer_time * 1000.0:.1f}ms.")
            print("=" * 60)
            print("[SUCCESS] Laya model is downloaded, verified, and cached locally.")
            print("=" * 60)
            return True
        else:
            print("[FAIL] Health check inference failed.")
            return False

    except Exception as e:
        print(f"[FAIL] Error loading model: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and verify Laya model weights locally.")
    parser.add_argument("--model", default="convaiinnovations/laya", help="Hugging Face model ID")
    parser.add_argument("--device", default="auto", help="Compute device ('auto', 'cpu', 'cuda')")
    args = parser.parse_args()

    success = download_and_verify(model_id=args.model, device=args.device)
    sys.exit(0 if success else 1)
