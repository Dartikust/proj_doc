"""Настройки: значения по умолчанию → .env → переменные окружения."""

import math
import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent


def load_settings(project_root=PROJECT_ROOT):
    root = Path(project_root)
    values = {**dotenv_values(root / '.env', encoding='utf-8-sig'), **os.environ}

    def value(name, default):
        return values.get(name) if values.get(name) not in (None, '') else default

    def integer(name, default, minimum=1, maximum=None):
        try:
            result = int(value(name, default))
        except (TypeError, ValueError):
            raise ValueError(f'{name}: требуется целое число.') from None
        if result < minimum or (maximum is not None and result > maximum):
            raise ValueError(f'{name}: значение вне допустимого диапазона.')
        return result

    def path(name, default):
        result = Path(value(name, default)).expanduser()
        return str(result if result.is_absolute() else (root / result).resolve())

    debug = str(value('APP_DEBUG', 'false')).lower().strip()
    if debug not in {'true', 'false', '1', '0', 'yes', 'no', 'on', 'off'}:
        raise ValueError('APP_DEBUG: укажите true или false.')
    try:
        score = float(value('SEARCH_MIN_SCORE', 0.3))
    except (TypeError, ValueError):
        raise ValueError('SEARCH_MIN_SCORE: требуется число от -1 до 1.') from None
    if not math.isfinite(score) or not -1 <= score <= 1:
        raise ValueError('SEARCH_MIN_SCORE: требуется число от -1 до 1.')

    return {
        'APP_HOST': value('APP_HOST', '127.0.0.1'),
        'APP_PORT': integer('APP_PORT', 5000, maximum=65535),
        'DEBUG': debug in {'true', '1', 'yes', 'on'},
        'SECRET_KEY': value('SECRET_KEY', None),
        'MAX_CONTENT_LENGTH': integer('MAX_UPLOAD_MB', 10) * 1024 * 1024,
        'DATABASE': path('DATABASE', 'instance/contracts.sqlite3'),
        'UPLOAD_FOLDER': path('UPLOAD_FOLDER', 'instance/uploads'),
        'SEARCH_MODEL_DIR': path('SEARCH_MODEL_DIR', 'instance/models'),
        'SEARCH_MIN_SCORE': score,
        'DOCUMENTS_PAGE_SIZE': integer('DOCUMENTS_PAGE_SIZE', 25),
    }
