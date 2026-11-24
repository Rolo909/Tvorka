"""Small jobs for the chat model that help the other sections: better prompts, translation, voice-over text.

Each task gives the messages to send and turns the answer into what the field needs.
Instructions are English (models follow them best); the user's text keeps its language
unless the task is translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# How an image or video model wants its prompt.
STYLE_HINTS = {
    "tags": ("a comma-separated list of short English phrases, most important first: subject, details, "
             "setting, lighting, style, quality words; at most 60 words (the model reads only ~75 tokens)"),
    "natural": ("one or two flowing English sentences in plain natural language: subject, setting, "
                "composition, lighting, mood and style; no tag lists, no weights in brackets"),
    "video": ("one English paragraph of 2–4 sentences describing a single continuous shot: the subject, what "
              "moves and how, the camera movement, the lighting and mood; nothing that needs cuts"),
}
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


@dataclass(frozen=True)
class Task:
    """A helper request: what to send and how many tokens the answer may take."""

    messages: list[dict[str, Any]]
    max_tokens: int = 400


def prompt_style(spec: Any) -> str:
    """tags (Stable Diffusion: a CLIP text encoder) | natural (FLUX, Sana… : T5 / an LLM) | video."""
    if getattr(spec, "kind", "") == "video":
        return "video"
    return "tags" if "unet" in (getattr(spec, "memory", {}) or {}) else "natural"


def needs_translation(text: str) -> bool:
    return bool(CYRILLIC.search(text))


def _system(text: str) -> dict[str, str]:
    return {"role": "system", "content": text}


def improve_prompt(prompt: str, style: str) -> Task:
    return Task([
        _system("You improve prompts for AI image and video generators. Keep the user's idea and every "
                "detail they gave, add what makes the picture vivid and concrete. "
                f"Write {STYLE_HINTS[style]}. Write in English even if the idea is in another language. "
                "Reply with the prompt only."),
        {"role": "user", "content": prompt},
    ])


def translate_prompt(prompt: str) -> Task:
    return Task([
        _system("Translate this prompt for an image or video generator into English. Keep its meaning, "
                "its order and its style (a tag list stays a tag list). Reply with the translation only."),
        {"role": "user", "content": prompt},
    ])


def negative_prompt(prompt: str, style: str) -> Task:
    return Task([
        _system("You write negative prompts for Stable Diffusion: what must NOT appear in the picture. "
                "Given the prompt, list the usual defects (blurry, extra fingers, watermark, text…) and the "
                "things that would spoil this particular picture. Comma-separated English phrases, "
                "at most 25 words. Reply with the list only."),
        {"role": "user", "content": prompt},
    ], 120)


def prompt_from_image(image_url: str, style: str) -> Task:
    """``image_url`` is a data URL; the model must see images."""
    return Task([
        _system(f"Describe the picture as a prompt for an image generator, so it can be redrawn: "
                f"{STYLE_HINTS[style]}. Reply with the prompt only."),
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}},
                                     {"type": "text", "text": "Write the prompt for this picture."}]},
    ])


def critique(prompt: str, image_url: str, style: str) -> Task:
    """Compare the result with what was asked; answer with a better prompt."""
    return Task([
        _system("You check images made by an AI generator. Compare the picture with the prompt it was made "
                "from: find what is missing or wrong. Then write an improved prompt that fixes it: "
                f"{STYLE_HINTS[style]}. Reply in exactly this form:\n"
                "PROBLEMS: <one short sentence in the language of the prompt>\n"
                "PROMPT: <the improved prompt>"),
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}},
                                     {"type": "text", "text": f"The prompt was: {prompt}"}]},
    ], 500)


def prepare_speech(text: str) -> Task:
    return Task([
        _system("You prepare text for a speech synthesizer. Fix spelling and punctuation, put the letter ё "
                "where it belongs in Russian, write numbers, dates, units, abbreviations and symbols out in "
                "words, split very long sentences, remove what cannot be read aloud (links, markup, emoji). "
                "Keep the language, the meaning and the order. Reply with the text only."),
        {"role": "user", "content": text},
    ], max(400, int(len(text) / 2)))


def translate_speech(text: str, language_code: str) -> Task:
    language = {"en": "English", "ru": "Russian"}.get(language_code, f"language {language_code}")
    return Task([
        _system(f"Translate the entire user text into fluent {language} for reading aloud. "
                f"Write every sentence in {language}. "
                "Keep its meaning, tone and paragraph breaks. Reply with the translated text only."),
        {"role": "user", "content": text},
    ], max(400, len(text) // 2))


def clean(answer: str) -> str:
    """The answer without what models add around it: quotes, code fences, "Prompt:" labels."""
    text = answer.strip()
    fence = re.fullmatch(r"```[\w-]*\n?(.*?)\n?```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"^\**\s*(?:improved |negative )?(?:prompt|translation|перевод|промпт)\s*:\s*\**\s*",
                  "", text, flags=re.IGNORECASE)
    pairs = {'"': '"', "'": "'", "«": "»", "“": "”"}
    if len(text) > 1 and pairs.get(text[0]) == text[-1]:
        text = text[1:-1]
    return text.strip()


def parse_critique(answer: str) -> tuple[str, str]:
    """``(problems, improved prompt)`` from an answer to :func:`critique`; the whole answer is the prompt
    when the model ignored the form."""
    problems = re.search(r"PROBLEMS\s*:\s*(.+?)(?:\n|$)", answer, flags=re.IGNORECASE)
    prompt = re.search(r"PROMPT\s*:\s*(.+)", answer, flags=re.IGNORECASE | re.DOTALL)
    if prompt is None:
        return "", clean(answer)
    return (problems.group(1).strip() if problems else ""), clean(prompt.group(1))
