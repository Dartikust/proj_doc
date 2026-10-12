"""Связывает чтение, нормализацию и извлечение в одну цепочку."""

from dataclasses import dataclass

from .extractor import extract_fields, normalize_text
from .readers import read_text


@dataclass
class Result:
    raw_text: str
    normalized_text: str
    fields: dict
    warnings: list[str]

    @property
    def status(self):
        return 'review' if self.warnings else 'extracted'


def process_document(content: bytes, extension: str) -> Result:
    raw_text = read_text(content, extension)
    normalized = normalize_text(raw_text)
    fields, warnings = extract_fields(normalized)
    return Result(raw_text, normalized, fields, warnings)
