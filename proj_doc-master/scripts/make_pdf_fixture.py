"""Пересоздание тестового PDF; только для разработки, требует reportlab."""

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


if __name__ == '__main__':
    output = Path('tests/fixtures/contract.pdf')
    output.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont('FixtureFont', 'C:/Windows/Fonts/arial.ttf'))
    pdf = canvas.Canvas(str(output), invariant=True)
    pdf.setFont('FixtureFont', 12)
    lines = [
        'Синтетический договор № PDF-007 от 17.03.2026',
        'Заказчик: ООО «Лектор»',
        'Исполнитель: ИП Петров Пётр Петрович',
        'Сумма договора: 125 000,50 руб.',
        'Аванс: 5 000 рублей. Срок оплаты до 31.12.2026.',
    ]
    for index, line in enumerate(lines):
        pdf.drawString(45, 790 - index * 30, line)
    pdf.showPage()
    pdf.setFont('FixtureFont', 12)
    pdf.drawString(45, 790, 'Вторая страница: учебный документ, все данные вымышлены.')
    pdf.save()
