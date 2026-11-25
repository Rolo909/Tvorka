"""Load a GGUF denoiser alongside an NF4 text encoder from local files."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from tvorka.core.catalog import GgufTransformer
from tvorka.engines.base import Context, EngineError


def load_gguf(diffusers: Any, base: Path, weights: Path, recipe: GgufTransformer,
              dtype: Any, ctx: Context, variant: str | None = None) -> Any:
    for package in ("gguf", "bitsandbytes"):
        if importlib.util.find_spec(package) is None:
            raise EngineError("gguf_dependencies", package)

    import torch
    from transformers import BitsAndBytesConfig, T5EncoderModel, UMT5EncoderModel

    if not torch.cuda.is_bf16_supported(including_emulation=False):
        raise EngineError("gguf_cuda", "Native BF16 is unavailable")
    with weights.open("rb") as handle:
        if handle.read(4) != b"GGUF":
            raise EngineError("load_failed", f"Invalid GGUF header: {weights.name}")

    if recipe.family == "flux":
        encoder_cls, transformer_cls, pipeline_cls = (
            T5EncoderModel, diffusers.FluxTransformer2DModel, diffusers.FluxPipeline)
    else:
        encoder_cls, transformer_cls, pipeline_cls = (
            UMT5EncoderModel, diffusers.WanTransformer3DModel, diffusers.WanPipeline)

    options = {"dtype": dtype, "local_files_only": True}
    format_options = {"use_safetensors": True, "variant": variant} if variant else {"use_safetensors": True}
    encoder = encoder_cls.from_pretrained(
        str(base / recipe.encoder), **options, **format_options, device_map={"": "cuda:0"},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                             bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True),
    )
    encoder.to("cpu")  # release VRAM before the denoiser starts loading, keeping the packed weights
    torch.cuda.empty_cache()
    ctx.check()
    ctx.progress(0.45, "load")
    transformer = transformer_cls.from_single_file(
        str(weights), config=str(base), subfolder="transformer", **options,
        quantization_config=diffusers.GGUFQuantizationConfig(compute_dtype=dtype),
    )
    ctx.check()
    components = {recipe.encoder: encoder, "transformer": transformer}
    if recipe.family == "wan":
        # Wan's original VAE uses FP32 during decoding.
        components["vae"] = diffusers.AutoencoderKLWan.from_pretrained(
            str(base / "vae"), dtype=torch.float32, local_files_only=True, **format_options,
        )
    return pipeline_cls.from_pretrained(str(base), **options, **components, **format_options)
