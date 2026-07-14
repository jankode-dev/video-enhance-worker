FROM runpod/worker-comfyui:5.8.5-base

# Video core nodovi (LoadVideo/GetVideoComponents/CreateVideo/SaveVideo) traze ComfyUI >= 0.3.68,
# ComfyMathExpression (FPS x2) je core od v0.24.0 — pin na v0.27.0, isto kao face-swap worker i pod
RUN cd /comfyui && \
    git fetch --all --tags && \
    git checkout v0.27.0 && \
    pip install -r requirements.txt

# SeedVR2 — pin na TACAN commit iz workflow-a (690cc39, AInVFX/numz collab repo)
# da se signature nodova (DiT/VAE loader split) 100% poklapa sa API JSON-om
RUN git clone https://github.com/AInVFX/ComfyUI-SeedVR2_VideoUpscaler.git \
        /comfyui/custom_nodes/ComfyUI-SeedVR2_VideoUpscaler && \
    cd /comfyui/custom_nodes/ComfyUI-SeedVR2_VideoUpscaler && \
    git checkout 690cc39379c1481159ddd451368dbf2295930fc6 && \
    pip install -r requirements.txt

# RIFE frame interpolation (bez cupy — RIFE mu ne treba, image ostaje manji)
RUN git clone https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git \
        /comfyui/custom_nodes/ComfyUI-Frame-Interpolation && \
    cd /comfyui/custom_nodes/ComfyUI-Frame-Interpolation && \
    pip install -r requirements-no-cupy.txt

# rife49.pth (~65MB) pecemo u image — inace se skida na SVAKOM cold startu
RUN mkdir -p /comfyui/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife && \
    wget -q -O /comfyui/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/rife49.pth \
        https://github.com/Fannovel16/ComfyUI-Frame-Interpolation/releases/download/models/rife49.pth

# SeedVR2 modeli su na network volume-u (models/SEEDVR2), NE u image-u
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
