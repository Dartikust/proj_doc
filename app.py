"""Запуск: python app.py. Данные хранятся в instance/."""

from io import BytesIO
import json
from pathlib import Path
import secrets
from uuid import uuid4

from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from app_config import load_settings

from contracts.pipeline import process_document
from contracts.readers import DocumentError
from contracts import storage
from contracts.search import SemanticSearch, SearchUnavailable


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        DATABASE=str(Path(app.instance_path) / 'contracts.sqlite3'),
        UPLOAD_FOLDER=str(Path(app.instance_path) / 'uploads'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SEARCH_MODEL_DIR=str(Path(app.instance_path) / 'models'),
        SEARCH_MIN_SCORE=0.3,
        DOCUMENTS_PAGE_SIZE=25,
    )
    app.config.update(load_settings())
    if config:
        app.config.update(config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        key_path = Path(app.instance_path) / 'secret.key'
        try:
            with key_path.open('x', encoding='utf-8') as key_file:
                key_file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = key_path.read_text(encoding='utf-8')
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    storage.initialize(app.config['DATABASE'])
    app.extensions['semantic_search'] = SemanticSearch(app.config['DATABASE'], app.config['SEARCH_MODEL_DIR'])

    @app.context_processor
    def csrf_context():
        session.setdefault('csrf_token', secrets.token_hex(32))
        return {'csrf_token': session['csrf_token']}

    @app.before_request
    def check_csrf():
        if request.method == 'POST':
            expected = session.get('csrf_token')
            received = request.form.get('csrf_token', '')
            if not expected or not secrets.compare_digest(expected, received):
                abort(400, description='Обновите страницу и повторите отправку формы.')

    @app.get('/')
    def home():
        documents = storage.list_documents(app.config['DATABASE'])
        return render_template('home.html', documents=documents)

    @app.get('/documents')
    def documents():
        query = request.args.get('q', '').strip()
        if len(query) > 500:
            abort(400, description='Поисковый запрос должен быть не длиннее 500 символов.')
        sort = request.args.get('sort', 'relevance' if query else 'recent')
        if sort == 'relevance' and not query:
            sort = 'recent'
        direction = request.args.get('direction', 'asc' if sort in {'customer', 'contractor'} else 'desc')
        if sort not in storage.SORT_FIELDS or direction not in {'asc', 'desc'}:
            abort(400, description='Выберите допустимый вариант сортировки.')
        try:
            page = max(1, int(request.args.get('page', '1')))
        except ValueError:
            abort(400, description='Некорректный номер страницы.')
        records = [dict(item) for item in storage.list_documents(app.config['DATABASE'])]
        total = len(records)
        search_error = None
        if query:
            try:
                records = app.extensions['semantic_search'].search(records, query, app.config['SEARCH_MIN_SCORE'])
            except SearchUnavailable as exc:
                app.logger.warning('Semantic search unavailable', exc_info=True)
                search_error = str(exc)
                records = []
        records = storage.sort_documents(records, sort, direction)
        count = len(records)
        size = app.config['DOCUMENTS_PAGE_SIZE']
        pages = max(1, (count + size - 1) // size)
        page = min(page, pages)
        return render_template('documents.html', documents=records[(page - 1) * size:page * size],
                               query=query, sort=sort, direction=direction, total=total, count=count,
                               page=page, pages=pages, search_error=search_error), 503 if search_error else 200

    @app.post('/upload')
    def upload():
        uploaded = request.files.get('document')
        if not uploaded or not uploaded.filename:
            flash('Выберите договор в формате PDF или DOCX.', 'error')
            return redirect(url_for('home'))
        original_name = uploaded.filename.replace('\\', '/').rsplit('/', 1)[-1][:200]
        extension = Path(original_name).suffix.lower()
        if extension not in {'.pdf', '.docx'}:
            flash('Поддерживаются только PDF и DOCX.', 'error')
            return redirect(url_for('home'))
        content = uploaded.read()
        try:
            result = process_document(content, extension)
        except DocumentError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('home'))
        stored_name = f'{uuid4().hex}{extension}'
        target = Path(app.config['UPLOAD_FOLDER']) / stored_name
        target.write_bytes(content)
        try:
            document_id = storage.save_document(app.config['DATABASE'], original_name, stored_name, result)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        flash('Договор обработан. Проверьте извлечённые поля по исходному тексту.', 'success')
        return redirect(url_for('document', document_id=document_id))

    @app.get('/documents/<int:document_id>')
    def document(document_id):
        item = storage.get_document(app.config['DATABASE'], document_id)
        if item is None:
            abort(404)
        return render_template('document.html', document=item, warnings=json.loads(item['warnings']))

    @app.get('/documents/<int:document_id>/download')
    def download(document_id):
        item = storage.get_document(app.config['DATABASE'], document_id)
        if item is None:
            abort(404)
        target = Path(app.config['UPLOAD_FOLDER']) / item['stored_name']
        if not target.is_file():
            abort(404)
        return send_file(target, as_attachment=True, download_name=item['original_name'])

    @app.get('/sample')
    def sample():
        from scripts.generate_dataset import make_document, sample_record
        buffer = BytesIO()
        make_document(sample_record(1), 'labels').save(buffer)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='sample-contract.docx',
                         mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    @app.get('/about')
    def about():
        return render_template('about.html')

    @app.get('/author')
    def author():
        return render_template('author.html')

    @app.get('/test')
    def test():
        return render_template('test.html')

    @app.errorhandler(RequestEntityTooLarge)
    def file_too_large(error):
        limit = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        return render_template('error.html', message=f'Файл слишком большой. Лимит запроса — {limit} МБ.'), 413

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('error.html', message=error.description), 400

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host=app.config['APP_HOST'], port=app.config['APP_PORT'], debug=app.config['DEBUG'], load_dotenv=False)
