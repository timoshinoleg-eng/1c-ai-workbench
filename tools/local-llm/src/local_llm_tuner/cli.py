from __future__ import annotations

import argparse
import ctypes
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Sequence


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


@dataclass(frozen=True)
class RuntimePlan:
    engine: str
    backend: str
    launcher: str
    model_path: str
    model_size_gib: float
    total_ram_gib: float | None
    host: str
    port: int
    threads: int
    threads_batch: int
    ctx_size: int
    batch_size: int
    ubatch_size: int
    parallel: int
    cache_type_k: str
    cache_type_v: str
    notes: list[str]
    command: list[str]


def _windows_total_ram_bytes() -> int | None:
    if os.name != "nt":
        return None

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys)


def _format_gib(size_bytes: int | None) -> float | None:
    if size_bytes is None:
        return None
    return round(size_bytes / (1024**3), 2)


def _choose_ctx_size(model_size_bytes: int, override: int | None) -> int:
    if override is not None:
        return override
    if model_size_bytes <= 3_000_000_000:
        return 8192
    if model_size_bytes <= 6_000_000_000:
        return 4096
    if model_size_bytes <= 8_000_000_000:
        return 3072
    return 2048


def _choose_batch_sizes(ctx_size: int) -> tuple[int, int]:
    if ctx_size >= 8192:
        return 384, 192
    if ctx_size >= 4096:
        return 256, 128
    if ctx_size >= 3072:
        return 192, 96
    return 128, 64


def _choose_notes(model_size_bytes: int, total_ram_bytes: int | None, ctx_size: int) -> list[str]:
    notes: list[str] = [
        "Use GGUF quantization: Q4_K_M first, Q5_K_M only if you can spare more RAM.",
        "Keep the GPU offload at zero on this machine; the AMD iGPU is not the fast path.",
        "Flash attention is not part of the baseline profile.",
    ]

    if total_ram_bytes is not None:
        total_ram_gib = total_ram_bytes / (1024**3)
        if model_size_bytes / (1024**3) > 8.0:
            notes.append(
                f"Model weights are large for 16 GB RAM; expect tight headroom at {total_ram_gib:.1f} GiB."
            )
        if ctx_size > 4096 and total_ram_gib < 18:
            notes.append("The larger context is only safe for smaller GGUFs on this box.")
    return notes


def build_plan(
    model_path: Path,
    ctx_override: int | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    launcher: str = "llama-server.exe",
) -> RuntimePlan:
    model_size_bytes = model_path.stat().st_size
    total_ram_bytes = _windows_total_ram_bytes()
    logical_cores = os.cpu_count() or 1
    physical_cores = max(1, logical_cores // 2)

    ctx_size = _choose_ctx_size(model_size_bytes, ctx_override)
    batch_size, ubatch_size = _choose_batch_sizes(ctx_size)

    command = [
        launcher,
        "-m",
        str(model_path),
        "--host",
        host,
        "--port",
        str(port),
        "--threads",
        str(physical_cores),
        "--threads-batch",
        str(logical_cores),
        "-c",
        str(ctx_size),
        "-b",
        str(batch_size),
        "-ub",
        str(ubatch_size),
        "--parallel",
        "1",
        "--mmap",
        "--cache-prompt",
        "--flash-attn",
        "off",
        "--cache-type-k",
        "q8_0",
        "--cache-type-v",
        "q8_0",
    ]

    return RuntimePlan(
        engine="llama.cpp",
        backend="cpu-avx2",
        launcher=launcher,
        model_path=str(model_path),
        model_size_gib=round(model_size_bytes / (1024**3), 2),
        total_ram_gib=_format_gib(total_ram_bytes),
        host=host,
        port=port,
        threads=physical_cores,
        threads_batch=logical_cores,
        ctx_size=ctx_size,
        batch_size=batch_size,
        ubatch_size=ubatch_size,
        parallel=1,
        cache_type_k="q8_0",
        cache_type_v="q8_0",
        notes=_choose_notes(model_size_bytes, total_ram_bytes, ctx_size),
        command=command,
    )


def _quote_powershell(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _render_command(command: Sequence[str]) -> str:
    rendered: list[str] = []
    for token in command:
        if any(char.isspace() for char in token) or token == "" or "'" in token:
            rendered.append(_quote_powershell(token))
        else:
            rendered.append(token)
    return " ".join(rendered)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a llama.cpp launch profile for this machine.")
    parser.add_argument("--model", required=True, type=Path, help="Path to a GGUF model file.")
    parser.add_argument("--ctx-size", type=int, default=None, help="Override the context size.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for llama-server.")
    parser.add_argument("--port", default=8080, type=int, help="Bind port for llama-server.")
    parser.add_argument(
        "--launcher",
        default="llama-server.exe",
        help="Launcher executable to emit in the final command.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the plan as JSON instead of a human-readable summary.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    model_path = args.model.expanduser().resolve()
    if not model_path.exists():
        raise SystemExit(f"Model file not found: {model_path}")

    plan = build_plan(model_path, args.ctx_size, args.host, args.port, args.launcher)

    if args.json:
        print(json.dumps(asdict(plan), indent=2))
        return 0

    print(f"Engine: {plan.engine}")
    print(f"Backend: {plan.backend}")
    print(f"Model: {plan.model_path} ({plan.model_size_gib} GiB)")
    if plan.total_ram_gib is not None:
        print(f"RAM: {plan.total_ram_gib} GiB")
    print(f"Threads: {plan.threads} / batch {plan.threads_batch}")
    print(f"Context: {plan.ctx_size}")
    print(f"Batch: {plan.batch_size} / ubatch {plan.ubatch_size}")
    print(f"KV cache: K={plan.cache_type_k} V={plan.cache_type_v}")
    print()
    print("Recommended launch:")
    print(_render_command(plan.command))
    print()
    for note in plan.notes:
        print(f"- {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
