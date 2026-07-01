# Local LLM Tuner

This helper is tuned for the current machine profile:

- CPU: AMD Ryzen 5 5500U, 6 physical cores / 12 logical processors
- RAM: 16 GB
- GPU: AMD Radeon integrated graphics with no practical CUDA path

On this class of hardware, the engine choice is `llama.cpp` with GGUF models.
That matches the X thread's guidance for "laptop / edge / odd hardware" and
keeps the runtime on the CPU AVX2 path instead of chasing CUDA-only stacks.

## Why this engine

- `llama.cpp` is the default fit for portability and low-memory systems.
- `vLLM` is the wrong target here; it wants a server-class GPU path.
- `TensorRT-LLM` is NVIDIA-only in practice.
- `SGLang` is useful for long-context routing and multi-model serving, not this laptop.

## Baseline launch profile

Start here for a GGUF model on this machine:

- `--threads 6`
- `--threads-batch 12`
- `--batch-size 256`
- `--ubatch-size 128`
- `--ctx-size 4096`
- `--parallel 1`
- `--cache-type-k q8_0`
- `--cache-type-v q8_0`
- `--mmap`
- `--cache-prompt`
- `--flash-attn off`

That keeps prompt processing busy, keeps generation on the physical cores, and
keeps the KV cache from eating the 16 GB budget.

## Setup

```powershell
cd C:\1c-ai-workbench\tools\local-llm
uv venv .venv
uv sync
```

`uv` will print a warning about the repository root `pyproject.toml` because
that file is used for tooling config only. The warning is harmless.

## Usage

Generate a launch command for a specific model:

```powershell
uv run local-llm-tune --model C:\models\your-model.gguf
```

If the model is small and you want a longer context, pass `--ctx-size 8192`.
If the model is larger than about 6 to 8 GB on disk, keep the context at 4096
or lower and do not expect this laptop to enjoy the ride.
