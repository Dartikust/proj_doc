"""Локальный семантический поиск по полному тексту и реквизитам."""

from hashlib import sha256
import json
from pathlib import Path
from threading import RLock

import numpy as np

from . import storage


MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
INDEX_VERSION = MODEL_NAME + ':paragraphs-words40-overlap10-v2'


class SearchUnavailable(RuntimeError):
    pass


def load_model(cache_dir, allow_download=False):
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache_dir),
                         threads=2, local_files_only=not allow_download)


def split_text(text, size=40, overlap=10):
    words = text.split()
    chunks = []
    for start in range(0, len(words), size - overlap):
        chunks.append(' '.join(words[start:start + size]))
        if start + size >= len(words):
            break
    return chunks


def document_chunks(document):
    metadata = '\n'.join(str(document.get(key) or '') for key in
                         ('original_name', 'number', 'date', 'customer', 'contractor', 'amount'))
    chunks = split_text(metadata)
    for paragraph in document['normalized_text'].splitlines():
        chunks.extend(split_text(paragraph))
    return chunks


class SemanticSearch:
    def __init__(self, database, cache_dir, encoder=None):
        self.database = database
        self.cache_dir = Path(cache_dir)
        self.encoder = encoder
        self.lock = RLock()

    def _model(self):
        if self.encoder is None:
            try:
                self.encoder = load_model(self.cache_dir)
            except Exception as exc:
                raise SearchUnavailable('Поиск по смыслу сейчас недоступен. Список и сортировка продолжают работать.') from exc
        return self.encoder

    def _encode(self, texts):
        vectors = np.asarray(list(self._model().embed(texts, batch_size=16)), dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(texts) or not np.isfinite(vectors).all():
            raise SearchUnavailable('Модель поиска вернула некорректный результат.')
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-12)

    def _index(self, document):
        chunks = document_chunks(document)
        fingerprint = sha256(json.dumps(chunks, ensure_ascii=False).encode('utf-8')).hexdigest()
        cached = storage.get_search_index(self.database, document['id'], INDEX_VERSION, fingerprint)
        if cached:
            vectors = np.frombuffer(cached['vectors'], dtype='<f4').reshape(-1, cached['dimensions'])
            return json.loads(cached['chunks']), vectors
        vectors = self._encode(chunks)
        storage.save_search_index(self.database, document['id'], INDEX_VERSION, fingerprint,
                                  chunks, vectors.astype('<f4').tobytes(), vectors.shape[1])
        return chunks, vectors

    def index_documents(self, documents):
        with self.lock:
            for document in documents:
                self._index(dict(document))

    def search(self, documents, query, min_score=0.3):
        if not documents:
            return []
        with self.lock:
            try:
                query_vector = self._encode([query.strip()])[0]
                hits = []
                for record in documents:
                    document = dict(record)
                    chunks, vectors = self._index(document)
                    scores = vectors @ query_vector
                    best = int(np.argmax(scores))
                    score = float(scores[best])
                    if score >= min_score:
                        document['score'] = score
                        document['snippet'] = chunks[best]
                        hits.append(document)
                return storage.sort_documents(hits, 'relevance', 'desc')
            except SearchUnavailable:
                raise
            except Exception as exc:
                raise SearchUnavailable('Поиск по смыслу сейчас недоступен. Список и сортировка продолжают работать.') from exc
