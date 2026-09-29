from pathlib import Path


def parse_contract(file_path: Path) -> dict:
    """Заглушка парсера.

    На следующем этапе сюда подключаются:
    - извлечение текста из PDF/DOCX;
    - RegEx / Natasha;
    - при необходимости NLP-модель.

    Остальной сайт менять для этого не потребуется.
    """
    return {
        "number": None,
        "date": None,
        "customer": None,
        "contractor": None,
        "amount": None,
        "raw_text": None,
        "status": "Ожидает обработки",
    }
