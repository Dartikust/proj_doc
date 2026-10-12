"""Простой baseline: явные подписи полей и типовая преамбула договора."""

from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata


MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
}
LABELS = {
    'number': 'номер договора', 'date': 'дата заключения',
    'customer': 'заказчик', 'contractor': 'исполнитель', 'amount': 'сумма договора',
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text).replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\u00ad', '')
    return '\n'.join(re.sub(r'[^\S\n]+', ' ', line).strip() for line in text.split('\n'))


def first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(' \t:;,.')
    return None


def parse_date(value):
    if not value:
        return None
    numeric = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', value)
    written = re.search(r'[«"“]?(\d{1,2})[»"”]?\s+([а-яё]+)\s+(\d{4})', value, re.I)
    try:
        if numeric:
            day, month, year = map(int, numeric.groups())
        elif written and written.group(2).lower() in MONTHS:
            day, month, year = int(written[1]), MONTHS[written[2].lower()], int(written[3])
        else:
            return None
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def extract_fields(text: str) -> tuple[dict, list[str]]:
    header = text[:2500]
    number = first_match([
        r'(?:номер\s+договора|договор(?:\s+[а-яё]+){0,5})\s*(?:№|N|:|номер)\s*([\w][\w/.-]*)',
    ], header)
    date_token = r'([«"“]?\d{1,2}(?:[./-]\d{1,2}[./-]\d{4}|[»"”]?\s+[а-яё]+\s+\d{4}))'
    date_value = first_match([
        r'дата\s+(?:заключения(?:\s+договора)?|договора)\s*[:—-]?\s*' + date_token,
        r'\bот\s+' + date_token,
        r'(?:^|\n)(?:г\.\s*[^\n]*?\s+)?' + date_token,
    ], header)

    fields = {'number': number, 'date': parse_date(date_value)}
    for key, role in [('customer', 'заказчик'), ('contractor', 'исполнитель')]:
        fields[key] = first_match([
            rf'(?:^|\n){role}\s*[:—-]\s*([^\n;]+)',
            rf'((?:ООО|АО|ПАО|ОАО|ЗАО)\s*[«"“][^»"”\n]+[»"”])\s*,?\s*именуем\w*\s+(?:в\s+дальнейшем\s+)?[«"“]?{role}',
            rf'((?:ИП)\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)\s*,?\s*именуем\w*\s+(?:в\s+дальнейшем\s+)?[«"“]?{role}',
        ], text)

    amount = first_match([
        r'(?:сумма\s+договора|(?:общая\s+)?стоимость\s+(?:договора|услуг|работ)|цена\s+договора)'
        r'\s*(?:[:—=-]|составляет)?\s*(\d[\d ]*(?:[.,]\d{1,2})?)\s*(?:\([^\n)]*\)\s*)?(?:руб(?:\.|лей|ля)?|₽|RUB)(?!\w)',
    ], text)
    fields['amount'] = None
    if amount:
        try:
            fields['amount'] = str(Decimal(amount.replace(' ', '').replace(',', '.')).quantize(Decimal('0.01')))
        except InvalidOperation:
            pass
    warnings = [f'Не найдено или не распознано поле: {label}.' for key, label in LABELS.items() if fields[key] is None]
    return fields, warnings
