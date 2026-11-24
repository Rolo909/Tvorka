"""Helper tasks for the chat model: what is asked and how the answer is cleaned."""

from __future__ import annotations

import pytest

from tvorka.core.catalog import Catalog
from tvorka.core.llm import prompts


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog()


def test_prompt_style_follows_the_model(catalog: Catalog) -> None:
    assert prompts.prompt_style(catalog.get("stabilityai/sd-turbo")) == "tags"
    assert prompts.prompt_style(catalog.get("stabilityai/sdxl-turbo")) == "tags"
    assert prompts.prompt_style(catalog.get("black-forest-labs/FLUX.1-schnell")) == "natural"
    assert prompts.prompt_style(catalog.get("THUDM/CogVideoX-2b")) == "video"


def test_tasks_carry_the_text_and_the_style() -> None:
    task = prompts.improve_prompt("маяк в шторм", "tags")
    assert task.messages[-1] == {"role": "user", "content": "маяк в шторм"}
    assert "comma-separated" in task.messages[0]["content"] and "English" in task.messages[0]["content"]
    assert "camera" in prompts.improve_prompt("x", "video").messages[0]["content"]
    picture = prompts.prompt_from_image("data:image/jpeg;base64,AAA", "natural").messages[-1]["content"]
    assert picture[0]["image_url"]["url"].startswith("data:image/jpeg")
    assert prompts.prepare_speech("а" * 4000).max_tokens == 2000  # long texts get room for the answer


def test_needs_translation() -> None:
    assert prompts.needs_translation("Маяк на скале") and prompts.needs_translation("a cat и пёс")
    assert not prompts.needs_translation("a lighthouse, 3D render")


@pytest.mark.parametrize(("answer", "clean"), [
    ("  a lighthouse, dusk  ", "a lighthouse, dusk"),
    ('"a lighthouse at dusk"', "a lighthouse at dusk"),
    ("«маяк»", "маяк"),
    ("Prompt: a lighthouse", "a lighthouse"),
    ("**Improved prompt:** a lighthouse", "a lighthouse"),
    ("```\na lighthouse, storm\n```", "a lighthouse, storm"),
    ("```text\nновый текст\n```", "новый текст"),
    ("Перевод: a cat", "a cat"),
])
def test_clean(answer: str, clean: str) -> None:
    assert prompts.clean(answer) == clean


def test_parse_critique() -> None:
    answer = "PROBLEMS: Нет корабля на горизонте.\nPROMPT: a lighthouse at dusk, a ship on the horizon"
    assert prompts.parse_critique(answer) == ("Нет корабля на горизонте.",
                                              "a lighthouse at dusk, a ship on the horizon")
    assert prompts.parse_critique("a better prompt") == ("", "a better prompt")
