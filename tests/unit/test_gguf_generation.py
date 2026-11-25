from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_advisor import machine

from tvorka.core import advisor, hub
from tvorka.core.catalog import Catalog, GgufTransformer
from tvorka.core.settings import Settings
from tvorka.core.store import ModelStore
from tvorka.engines import diffusers_gguf
from tvorka.engines.base import EngineError
from tvorka.workers import download_proc

FLUX = "tvorka/flux1-schnell-gguf"
WAN = "tvorka/wan21-t2v-13b-gguf"
MB = 1024**2


@pytest.mark.parametrize("model_id", [FLUX, WAN])
def test_advisor_accounts_for_nf4_load_and_uses_component_offload(model_id: str) -> None:
    spec = Catalog().get(model_id)
    fit = advisor.assess(spec, machine(8), mode="low_memory")

    assert fit.ok and fit.plan.mode == "offload" and fit.plan.dtype == "bf16"
    assert spec.gguf_transformer.encoder_load_gb <= fit.need_vram_gb < 8
    assert ("gguf_offload", {}) in fit.notes
    assert not advisor.assess(spec, machine(6)).ok
    assert not advisor.assess(spec, machine(8, ram=8)).ok
    assert not advisor.assess(spec, machine(8), mode="cpu").ok


def test_advisor_rejects_nvidia_without_native_bf16() -> None:
    spec = Catalog().get(FLUX)
    hw = machine(8)
    hw = replace(hw, gpus=(replace(hw.gpus[0], cuda_capability=(7, 5)),))

    fit = advisor.assess(spec, hw)

    assert not fit.ok and ("gguf_cuda", {}) in fit.notes


def test_recipe_rejects_paths_in_place_of_gguf_filenames() -> None:
    with pytest.raises(ValueError, match="invalid GGUF"):
        GgufTransformer("author/model", "../other.gguf", "flux")


def test_loader_explains_missing_cuda_extra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recipe = GgufTransformer("author/weights", "model.gguf", "flux")
    monkeypatch.setattr(diffusers_gguf.importlib.util, "find_spec", lambda _package: None)

    with pytest.raises(EngineError) as failure:
        diffusers_gguf.load_gguf(None, tmp_path, tmp_path / recipe.file, recipe, None, None)

    assert failure.value.code == "gguf_dependencies"


def base_files(encoder: str) -> list[tuple[str, int]]:
    return [("model_index.json", 100), ("transformer/config.json", 20),
            ("transformer/diffusion_pytorch_model.safetensors", 2_000 * MB),
            (f"{encoder}/config.json", 20), (f"{encoder}/model.safetensors", 200 * MB),
            (f"{encoder}/model.fp16.safetensors", 100 * MB), (f"{encoder}/pytorch_model.bin", 200 * MB),
            ("vae/config.json", 20), ("vae/diffusion_pytorch_model.safetensors", 200 * MB),
            ("vae/diffusion_pytorch_model.fp16.safetensors", 100 * MB), ("tokenizer/spiece.model", 50)]


def test_gguf_plan_keeps_configs_and_compact_safe_encoder_weights() -> None:
    plan = hub.plan_gguf_base(base_files("text_encoder"), "text_encoder")

    assert plan.variant == "fp16"
    selected = {"transformer/config.json", "text_encoder/model.fp16.safetensors", "tokenizer/spiece.model"}
    assert selected <= set(plan.files)
    assert "transformer" not in plan.components
    assert "text_encoder/pytorch_model.bin" not in plan.files
    assert "text_encoder/model.safetensors" not in plan.files


def test_composite_download_and_delete_keep_regular_base_separate(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = Catalog()
    spec = catalog.get(WAN)
    recipe = spec.gguf_transformer
    store = ModelStore(Settings(models_dir=str(tmp_path / "models")))
    regular = store.hub_repo_dir(catalog.get(spec.repo_id))
    regular.mkdir(parents=True)
    calls: list[tuple[str, str | None]] = []

    def siblings(repo: str, _token: str | None, revision: str = "") -> tuple:
        if repo == recipe.repo:
            return SimpleNamespace(sha="gguf-commit"), [(recipe.file, 512)]
        assert revision == recipe.base_revision
        return SimpleNamespace(sha=revision), base_files(recipe.encoder)

    def snapshot(repo: str, plan: hub.DownloadPlan, cache: Path, _token: str | None,
                 revision: str | None) -> str:
        calls.append((repo, revision))
        output = cache / repo.replace("/", "--")
        for name in plan.files:
            file = output / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"GGUF" if name == recipe.file else b"{}")
        return str(output)

    monkeypatch.setattr(hub, "repo_siblings", siblings)
    monkeypatch.setattr(download_proc, "_cache_snapshot", snapshot)
    monkeypatch.setattr(download_proc, "check_disk", lambda _cache, _need: None)
    result = download_proc._download_gguf(store.download_task(spec))
    manifest = store.manifest_path(spec)
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(result), encoding="utf-8")

    assert calls == [(spec.repo_id, recipe.base_revision), (recipe.repo, "gguf-commit")]
    assert store.is_installed(spec) and store.variant(spec) == "fp16"
    assert store.transformer_path(spec).name == recipe.file

    store.delete(spec)

    assert regular.exists() and not store.files_dir(spec).exists()
    assert not store.is_installed(spec)


@pytest.mark.parametrize("family, encoder_key", [("flux", "text_encoder_2"), ("wan", "text_encoder")])
def test_loader_supplies_offline_quantized_components(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                       family: str, encoder_key: str) -> None:
    trace: list[tuple[str, Any]] = []

    class Encoder:
        @staticmethod
        def from_pretrained(path: str, **kwargs: Any) -> Encoder:
            assert Path(path).name == encoder_key
            trace.append(("encoder", kwargs))
            return Encoder()

        def to(self, device: str) -> None:
            trace.append(("move_encoder", device))

    class Transformer:
        @staticmethod
        def from_single_file(path: str, **kwargs: Any) -> str:
            assert Path(path).read_bytes().startswith(b"GGUF")
            trace.append(("denoiser", kwargs))
            return "denoiser"

    class Pipeline:
        @staticmethod
        def from_pretrained(path: str, **kwargs: Any) -> str:
            assert Path(path) == tmp_path
            trace.append(("pipeline", kwargs))
            return "pipeline"

    torch = SimpleNamespace(cuda=SimpleNamespace(is_bf16_supported=lambda **_kwargs: True,
                                                empty_cache=lambda: None), float32="fp32")
    transformers = SimpleNamespace(T5EncoderModel=Encoder, UMT5EncoderModel=Encoder,
                                   BitsAndBytesConfig=lambda **options: options)
    diffusers = SimpleNamespace(FluxTransformer2DModel=Transformer, WanTransformer3DModel=Transformer,
                                 FluxPipeline=Pipeline, WanPipeline=Pipeline,
                                 GGUFQuantizationConfig=lambda **options: options,
                                 AutoencoderKLWan=SimpleNamespace(from_pretrained=lambda *_a, **kw: kw))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setattr(diffusers_gguf.importlib.util, "find_spec", lambda _package: object())
    recipe = GgufTransformer("author/weights", "model.gguf", family)
    weights = tmp_path / recipe.file
    weights.write_bytes(b"GGUF")
    ctx = SimpleNamespace(check=lambda: None, progress=lambda *_args: None)

    pipe = diffusers_gguf.load_gguf(diffusers, tmp_path, weights, recipe, "bf16", ctx, "fp16")

    assert pipe == "pipeline"
    [encoder, moved, denoiser, pipeline] = trace
    assert moved == ("move_encoder", "cpu")
    assert encoder[1]["quantization_config"]["bnb_4bit_quant_type"] == "nf4"
    assert encoder[1]["variant"] == "fp16" and encoder[1]["local_files_only"]
    assert denoiser[1]["config"] == str(tmp_path) and denoiser[1]["subfolder"] == "transformer"
    assert pipeline[1]["local_files_only"] and pipeline[1]["transformer"] == "denoiser"
    assert isinstance(pipeline[1][encoder_key], Encoder)
