import gc
import math
import subprocess
from pathlib import Path

import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video

MODEL = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"

LOCAL_MODEL = (
    "/root/.cache/huggingface/hub/"
    "models--Wan-AI--Wan2.1-T2V-1.3B-Diffusers/"
    "snapshots/0fad780a534b6463e45facd96134c9f345acfa5b"
)

_PIPE = None

def set_pipeline(pipeline):
    global _PIPE
    _PIPE = pipeline

def load_pipeline():
    global _PIPE

    if _PIPE is not None:
        return _PIPE

    print("Loading Wan 2.1 from local cache...")

    local_path = Path(LOCAL_MODEL)

    if (local_path / "model_index.json").exists():
        print("Using local Wan cache...")
        _PIPE = WanPipeline.from_pretrained(
            str(local_path),
            torch_dtype=torch.float16,
            local_files_only=True
        )
    else:
        print("Downloading Wan model from Hugging Face...")
        _PIPE = WanPipeline.from_pretrained(
            MODEL,
            torch_dtype=torch.float16
        )

    _PIPE.enable_model_cpu_offload()
    return _PIPE

def generate_video(prompt, output_path, duration=5, on_retry=None, visual_style="cartoon"):
    if not prompt or not prompt.strip():
        raise ValueError("Empty scene prompt.")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required.")

    duration = max(1, min(14, int(duration)))

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pipeline = load_pipeline()

    # Each generated clip contains 33 NEW AI frames.
    fps = 16
    frames_per_clip = 33
    clip_duration = frames_per_clip / fps
    clip_count = math.ceil(duration / clip_duration)

    work_dir = output_path.parent / (output_path.stem + "_parts")
    work_dir.mkdir(parents=True, exist_ok=True)

    raw_files = []

    # Every subject is rendered as polished, unmistakably animated 3D explainer content.
    # Keep the parameter for caller compatibility; no topic may switch to live-action.
    segment_guidance = (
        "Stylized premium 3D animated educational explainer, clearly computer-animated "
        "and never live-action, photorealistic footage, stock footage or documentary "
        "reconstruction. Use appealing designed shapes, refined materials, clean silhouettes, "
        "rich but controlled colors, bright readable cinematic lighting and smooth intentional "
        "camera movement. The result should feel like a high-quality animated explainer for "
        "a general audience, mature and visually engaging rather than childish or toy-like. "
        "Keep the same subject identity, geometry, proportions, color palette, materials, "
        "component layout and environment across adjoining segments. Show only the subject "
        "and action described by the scene prompt. Use accurate physical relationships, "
        "clear educational staging and meaningful motion. No unrelated objects, no live-action "
        "look, no text, labels, logos or watermarks."
    )

    print("Generating", clip_count, "unique AI clips...")
    print("Target duration:", duration, "seconds")

    for i in range(clip_count):
        raw_path = work_dir / f"part_{i:02d}.mp4"

        scene_prompt = (
            prompt.strip()
            + ". " + segment_guidance
            + f" This is animated segment {i + 1} of {clip_count} from the SAME scene; "
              "continue the same action and do not introduce a new subject or location."
        )

        print(f"Generating clip {i + 1}/{clip_count}...")

        result = pipeline(
            prompt=scene_prompt,
            height=832,
            width=480,
            num_frames=frames_per_clip,
            num_inference_steps=20,
            guidance_scale=5.0,
            generator=torch.Generator("cuda").manual_seed(
                20261115 + i * 7919
            )
        )

        export_to_video(
            result.frames[0],
            str(raw_path),
            fps=fps
        )

        raw_files.append(raw_path)

        del result
        gc.collect()
        torch.cuda.empty_cache()

    # Join independently generated clips without looping.
    concat_file = work_dir / "concat.txt"

    with open(concat_file, "w") as f:
        for raw in raw_files:
            safe_path = str(raw).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    print("Joining unique clips with FFmpeg...")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-t", str(duration),
        "-vf", "scale=480:832:flags=lanczos,fps=24,setsar=1",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path)
    ], check=True, capture_output=True, text=True)

    if not output_path.exists() or output_path.stat().st_size < 1000:
        raise RuntimeError("Video output is missing or too small.")

    print("SUCCESS:", output_path)
    print("Size:", round(output_path.stat().st_size / 1024**2, 2), "MB")

    return str(output_path)
    
