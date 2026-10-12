"""Однократно загрузить модель и подготовить индекс загруженных договоров."""

from pathlib import Path

from app import create_app
from contracts import storage
from contracts.search import SemanticSearch, load_model, MODEL_NAME


if __name__ == '__main__':
    app = create_app()
    cache_dir = Path(app.config['SEARCH_MODEL_DIR'])
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f'Preparing local model: {MODEL_NAME}', flush=True)
    encoder = load_model(cache_dir, allow_download=True)
    service = SemanticSearch(app.config['DATABASE'], cache_dir, encoder=encoder)
    documents = storage.list_documents(app.config['DATABASE'])
    service.index_documents(documents)
    print(f'Ready. Indexed documents: {len(documents)}', flush=True)
