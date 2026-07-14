#!/usr/bin/env python3
"""
Minimal client for the scail2-enhance serverless endpoint (SeedVR2 + RIFE x2).

Usage:
  export RUNPOD_API_KEY=xxxxx
  export RUNPOD_ENDPOINT_ID=xxxxx
  python client.py input.mp4 [--resolution 1080] [--multiplier 2] [--fps 60] ...

input.mp4 -> LoadVideo node 21 (name in payload MUST be "input.mp4")
Output    -> SaveVideo node 23 (mp4, base64 or S3 URL)
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib import request as urlrequest

API_KEY = os.environ.get("RUNPOD_API_KEY")
ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")
WORKFLOW_PATH = Path(__file__).parent / "workflow" / "scail2_stage2_enhance_api.json"


def b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urlrequest.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urlrequest.urlopen(req, timeout=1800) as resp:
        return json.loads(resp.read().decode())


def get(url: str) -> dict:
    req = urlrequest.Request(url, headers={"Authorization": f"Bearer {API_KEY}"})
    with urlrequest.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    if not API_KEY or not ENDPOINT_ID:
        sys.exit("Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID env vars first.")

    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Input video (e.g. SCAIL2 stage1 raw mp4)")
    ap.add_argument("--resolution", type=int, default=None, help="SeedVR2 target short-side res (default 1080, node 10)")
    ap.add_argument("--seed", type=int, default=None, help="SeedVR2 seed (node 10)")
    ap.add_argument("--batch-size", type=int, default=None, help="SeedVR2 batch_size, 4n+1 (default 33, node 10)")
    ap.add_argument("--blocks-to-swap", type=int, default=None, help="DiT blocks_to_swap; 0 on 48GB GPU for speed (node 14)")
    ap.add_argument("--dit-model", default=None, help="DiT model on volume, e.g. seedvr2_ema_7b_sharp_fp16.safetensors (node 14)")
    ap.add_argument("--multiplier", type=int, default=None, help="RIFE interpolation multiplier (default 2, nodes 50+51)")
    ap.add_argument("--fps", type=float, default=None, help="FORCE output fps (replaces auto fps*multiplier, node 24)")
    ap.add_argument("--async", dest="use_async", action="store_true", help="Use /run + polling instead of /runsync (for long videos)")
    args = ap.parse_args()

    wf = json.loads(WORKFLOW_PATH.read_text())

    if args.resolution is not None:
        wf["10"]["inputs"]["resolution"] = args.resolution
    if args.seed is not None:
        wf["10"]["inputs"]["seed"] = args.seed
    if args.batch_size is not None:
        wf["10"]["inputs"]["batch_size"] = args.batch_size
    if args.blocks_to_swap is not None:
        wf["14"]["inputs"]["blocks_to_swap"] = args.blocks_to_swap
    if args.dit_model is not None:
        wf["14"]["inputs"]["model"] = args.dit_model
    if args.multiplier is not None:
        wf["50"]["inputs"]["multiplier"] = args.multiplier
        wf["51"]["inputs"]["expression"] = f"a * {args.multiplier}"
    if args.fps is not None:
        # zameni link ka math nodu fiksnom vrednoscu
        wf["24"]["inputs"]["fps"] = args.fps

    payload = {
        "input": {
            "workflow": wf,
            "images": [
                {"name": "input.mp4", "image": b64(args.video)},
            ],
        }
    }

    base = f"https://api.runpod.ai/v2/{ENDPOINT_ID}"
    t0 = time.time()

    if args.use_async:
        print("Submitting job (run, async)...")
        job = post(f"{base}/run", payload)
        job_id = job["id"]
        while True:
            result = get(f"{base}/status/{job_id}")
            status = result.get("status")
            if status in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                break
            print(f"  status: {status} ({time.time() - t0:.0f}s)")
            time.sleep(10)
    else:
        print("Submitting job (runsync)...")
        result = post(f"{base}/runsync", payload)
        status = result.get("status")

    if status != "COMPLETED":
        print(json.dumps(result, indent=2)[:4000])
        sys.exit(f"Job status: {status}")

    outputs = result.get("output", {}).get("images", [])
    if not outputs:
        sys.exit("No files in output.")

    for i, item in enumerate(outputs):
        name = item.get("filename", f"enhanced_{i}.mp4")
        if item.get("type") == "base64":
            out = Path(name).name
            Path(out).write_bytes(base64.b64decode(item["data"]))
            print(f"Saved {out}")
        else:
            print(f"Output URL: {item['data']}")

    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
