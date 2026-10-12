"""Реальная модель: RUN_SEMANTIC_MODEL_TESTS=1 перед unittest discover."""

import os
from pathlib import Path
import tempfile
import unittest

from contracts import storage
from contracts.search import SemanticSearch, load_model


@unittest.skipUnless(os.environ.get('RUN_SEMANTIC_MODEL_TESTS') == '1', 'Enable tests with locally downloaded model')
class RealSemanticModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoder = load_model(Path(__file__).resolve().parents[1] / 'instance' / 'models')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database = str(Path(self.directory.name) / 'database.sqlite3')
        storage.initialize(database)
        self.search = SemanticSearch(database, self.directory.name, encoder=self.encoder)
        self.documents = [
            {'id': 1, 'normalized_text': 'Исполнитель проводит обучение сотрудников работе с бухгалтерской программой. Занятия включают практические упражнения и итоговую проверку знаний.'},
            {'id': 2, 'normalized_text': 'Подрядчик выполняет ремонт офиса: окраску стен, замену напольного покрытия и установку новых окон.'},
            {'id': 3, 'normalized_text': 'Настройка антивируса, резервное копирование и предотвращение утечек данных из корпоративной сети.'},
        ]

    def tearDown(self):
        self.directory.cleanup()

    def test_russian_paraphrases_rank_correct_documents(self):
        for query, expected in [('повышение квалификации персонала', 1), ('восстановление помещения', 2), ('защита информации', 3)]:
            with self.subTest(query=query):
                hits = self.search.search(self.documents, query)
                self.assertTrue(hits)
                self.assertEqual(hits[0]['id'], expected)

    def test_long_contract_tail_is_searchable_with_real_model(self):
        text = 'Ежемесячные платежи согласованы сторонами. ' * 100
        document = {'id': 4, 'normalized_text': text + self.documents[1]['normalized_text']}
        hits = self.search.search([document, self.documents[0]], 'восстановление помещения')
        self.assertEqual(hits[0]['id'], 4)
        self.assertIn('ремонт офиса', hits[0]['snippet'])
