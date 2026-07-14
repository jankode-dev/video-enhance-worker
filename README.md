# scail2-enhance-worker

RunPod **serverless** worker za SCAIL2 STAGE 2 Enhance workflow:
**SeedVR2 3B upscale (→1080p) + RIFE ×2 frame interpolacija (30→60fps), audio ostaje sinhronizovan.**

Baziran na [`runpod/worker-comfyui`](https://github.com/runpod-workers/worker-comfyui), isti šablon kao `z-image-face-swap-worker`. Modeli se učitavaju sa **network volume-a**; custom nodovi + `rife49.pth` su upečeni u Docker image.

---

## Šta je unutra

| Fajl | Svrha |
| --- | --- |
| `Dockerfile` | worker-comfyui 5.8.5-base + ComfyUI v0.27.0 + SeedVR2 (pin commit 690cc39) + RIFE + rife49.pth |
| `extra_model_paths.yaml` | Pokazuje ComfyUI na network volume (uklj. `seedvr2:` mapiranje) |
| `workflow/scail2_stage2_enhance_api.json` | API-format workflow (compute path, bez note/preview nodova) |
| `test_input.json` | curl payload template |
| `client.py` | Python test klijent |
| `.github/workflows/build.yml` | Push na `main` → build & push `janko24/scail2-enhance-worker:latest` |

---

## Preduslovi

### 1. Modeli na network volume-u

Base path: `/runpod-volume/runpod-slim/ComfyUI/`

```
models/SEEDVR2/seedvr2_ema_3b_fp16.safetensors    ← ~7 GB (HF: numz/SeedVR2_comfyUI)
models/SEEDVR2/ema_vae_fp16.safetensors           ← VAE
```

Opciono za oštrije rezultate na 48GB GPU: `models/SEEDVR2/seedvr2_ema_7b_sharp_fp16.safetensors` (biraš per-request preko `--dit-model`).

`rife49.pth` je **upečen u image**, ne treba na volume-u. Ako modeli fale na volume-u, SeedVR2 node će pokušati da ih skine sa HuggingFace-a u `models/SEEDVR2/` na volume-u (jednokratno, ali produžava prvi job).

### 2. Docker Hub secret

Repo secret **`DOCKERHUB_TOKEN`** (Settings → Secrets → Actions). Workflow se loguje kao `janko24`.

---

## Build

Push na `main` → GitHub Action automatski build-uje i push-uje.

Ručno:
```
docker build --platform linux/amd64 -t janko24/scail2-enhance-worker:latest .
docker push janko24/scail2-enhance-worker:latest
```

---

## Deploy na RunPod Serverless

1. **Serverless → New Endpoint → Import from Docker Registry**
2. Image: `janko24/scail2-enhance-worker:latest`
3. Zakači **network volume** sa modelima
4. GPU: **48 GB preporučeno** (L40S/A6000) — SeedVR2 na 1080p sa batch_size 33 je zahtevan.
   Na 48GB pošalji `--blocks-to-swap 0` za znatno brži job (default 32 je za štednju VRAM-a).
   24 GB (4090/L4) radi sa default podešavanjima (blocks_to_swap 32 + VAE tiling), ali sporije.
5. **Execution timeout**: podigni (video jobovi traju minutima).
6. **VAŽNO — S3 output**: enhanced 1080p60 mp4 lako pređe limit base64 odgovora.
   Podesi S3 env varijable na endpointu (`BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`,
   `BUCKET_SECRET_ACCESS_KEY`) da worker vraća URL umesto base64.

---

## API korišćenje

Jedan input video + workflow JSON. `name` mora biti `input.mp4` (LoadVideo node **21**).

> Limit veličine requesta: ~10MB za `/run`, ~20MB za `/runsync` — stage1 klipovi (640×360) staju bez problema.

### curl

```
curl -X POST \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d @request.json \
  https://api.runpod.ai/v2/<ENDPOINT_ID>/run
```

### Python

```
export RUNPOD_API_KEY=xxxxx
export RUNPOD_ENDPOINT_ID=xxxxx
python client.py stage1_raw.mp4 --blocks-to-swap 0 --async
```

Output: `output.images` → mp4 (base64 ili S3 URL), iz SaveVideo noda **23**.

---

## Per-request patches

| Node | Polje | Default | Napomena |
| --- | --- | --- | --- |
| `10` SeedVR2VideoUpscaler | `resolution` | 1080 | može 1440 na 48GB |
| `10` | `seed`, `batch_size` | 42, 33 | batch_size mora biti 4n+1 |
| `14` SeedVR2LoadDiTModel | `model` | `seedvr2_ema_3b_fp16.safetensors` | 7b_sharp za oštrije |
| `14` | `blocks_to_swap` | 32 | **0 na 48GB = mnogo brže** |
| `50` RIFE VFI | `multiplier` | 2 | ×2 interpolacija |
| `51` ComfyMathExpression | `expression` | `a * 2` | drži usklađeno sa multiplier-om |
| `24` CreateVideo | `fps` | link (fps×2) | `--fps 60` forsira fiksnu vrednost |

---

## Izmena workflow-a

Učitaj UI JSON u ComfyUI, izmeni, pa **Workflow → Export (API)** i prepiši
`workflow/scail2_stage2_enhance_api.json`. Izbaci Note/Markdown nodove pre exporta.
TorchCompile node iz UI verzije je bypass-ovan i namerno izostavljen iz API JSON-a.

## Napomene

- Custom nodovi idu **u Docker image**, modeli **na volume** — isto kao face-swap worker.
- SeedVR2 je pinovan na commit `690cc39` (isti kao u workflow JSON-u) da se signature
  nodova ne pomeri kad upstream izbaci breaking change.
- Ako job padne sa OOM: smanji `batch_size` (29 → 21 → 13), pa tek onda `resolution`.
