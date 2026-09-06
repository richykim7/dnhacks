"""Explicit numerical execution settings shared by e-value training tools."""

import torch


def execution(device="cpu", dtype="float64"):
    if dtype not in {"float32", "float64"}:
        raise ValueError("dtype must be float32 or float64")
    try:
        target = torch.device(device)
    except (RuntimeError, TypeError) as exc:
        raise ValueError("device must be cpu or cuda[:index]") from exc
    if target.type not in {"cpu", "cuda"} or (
        target.type == "cpu" and target.index is not None
    ):
        raise ValueError("device must be cpu or cuda[:index]")
    if target.type == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("CUDA requested but unavailable; choose cpu explicitly")
        index = torch.cuda.current_device() if target.index is None else target.index
        if index >= torch.cuda.device_count():
            raise ValueError("CUDA device index is unavailable")
        target = torch.device("cuda", index)
    metadata = dict(
        device=str(target),
        dtype=dtype,
        cuda_version=torch.version.cuda,
        device_name=torch.cuda.get_device_name(target)
        if target.type == "cuda"
        else "CPU",
    )
    return target, getattr(torch, dtype), metadata
