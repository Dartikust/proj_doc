"""PDF/DOCX → текст. Сканированные PDF требуют отдельного OCR-этапа."""

from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader


class DocumentError(ValueError):
    """Ошибка документа, которую можно показать пользователю."""


def read_text(content: bytes, extension: str) -> str:
    try:
        if extension == '.pdf':
            if not content.startswith(b'%PDF-'):
                raise DocumentError('Файл не похож на PDF. Проверьте его содержимое.')
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise DocumentError('PDF защищён паролем. Загрузите копию без защиты.')
            if len(reader.pages) > 100:
                raise DocumentError('Допустимо не более 100 страниц PDF.')
            parts = []
            length = 0
            for page in reader.pages:
                part = page.extract_text() or ''
                length += len(part)
                if length > 1_000_000:
                    raise DocumentError('В документе слишком много текста.')
                parts.append(part)
            text = '\n'.join(parts)
        elif extension == '.docx':
            with ZipFile(BytesIO(content)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 30 * 1024 * 1024:
                    raise DocumentError('Распакованный DOCX превышает 30 МБ.')
                if 'word/document.xml' not in archive.namelist():
                    raise DocumentError('В файле отсутствует содержимое Word.')
            document = Document(BytesIO(content))
            parts = []
            for block in document.iter_inner_content():
                if isinstance(block, Table):
                    parts.extend(' : '.join(cell.text for cell in row.cells) for row in block.rows)
                else:
                    parts.append(block.text)
            text = '\n'.join(parts)
        else:
            raise DocumentError('Поддерживаются только PDF и DOCX.')
    except DocumentError:
        raise
    except Exception as exc:
        # Детали стороннего парсера остаются причиной исключения, а не HTML-ответом.
        raise DocumentError('Не удалось прочитать документ. Возможно, он повреждён.') from exc

    if len(text) > 1_000_000:
        raise DocumentError('В документе слишком много текста.')
    if not text.strip():
        raise DocumentError('Текст не найден. Для PDF-сканов нужно OCR, которого пока нет.')
    return text
