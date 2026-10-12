from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from app import create_app
from contracts import storage
from contracts.pipeline import Result
from contracts.search import SemanticSearch, SearchUnavailable, split_text


class SortingTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {'id': 1, 'amount': '9.50', 'date': '2026-12-01', 'customer': 'Бета', 'contractor': 'Яна'},
            {'id': 2, 'amount': '100.05', 'date': '2026-01-02', 'customer': 'альфа', 'contractor': 'Алексей'},
            {'id': 3, 'amount': '900.50', 'date': '2026-07-15', 'customer': 'Вега', 'contractor': 'Мария'},
            {'id': 4, 'amount': None, 'date': None, 'customer': None, 'contractor': None},
        ]

    def test_all_four_fields_both_directions_nulls_last(self):
        expected = {'amount': [1, 2, 3], 'date': [2, 3, 1], 'customer': [2, 1, 3], 'contractor': [2, 3, 1]}
        for field, order in expected.items():
            for direction in ['asc', 'desc']:
                with self.subTest(field=field, direction=direction):
                    result = storage.sort_documents(self.records, field, direction)
                    self.assertEqual([item['id'] for item in result],
                                     (order if direction == 'asc' else order[::-1]) + [4])

    def test_money_keeps_decimal_precision(self):
        records = [{'id': 1, 'amount': '9007199254740992.02'}, {'id': 2, 'amount': '9007199254740992.01'}]
        self.assertEqual([item['id'] for item in storage.sort_documents(records, 'amount', 'asc')], [2, 1])


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = str(Path(self.directory.name) / 'database.sqlite3')
        storage.initialize(self.database)
        self.encoder = Mock()
        self.encoder.embed.side_effect = lambda texts, **kwargs: [
            np.array([1., 0.]) if 'ремонт' in text else np.array([0., 1.]) for text in texts]
        self.service = SemanticSearch(self.database, self.directory.name, encoder=self.encoder)
        self.document = {'id': 1, 'normalized_text': 'ремонт офиса', 'original_name': 'contract.docx'}

    def tearDown(self):
        self.directory.cleanup()

    def test_cache_survives_restart_and_updates_after_content_change(self):
        hits = self.service.search([self.document], 'ремонт', 0.5)
        self.assertEqual(hits[0]['snippet'], 'ремонт офиса')
        self.assertEqual(self.encoder.embed.call_count, 2)  # query + document chunks
        restarted = SemanticSearch(self.database, self.directory.name, encoder=self.encoder)
        restarted.search([self.document], 'ремонт', 0.5)
        self.assertEqual(self.encoder.embed.call_count, 3)  # only query
        self.document['normalized_text'] = 'доставка мебели'
        self.assertEqual(restarted.search([self.document], 'ремонт', 0.5), [])
        self.assertEqual(self.encoder.embed.call_count, 5)  # changed document reindexed

    def test_search_checks_end_of_long_document(self):
        self.document['normalized_text'] = ('поставка мебели ' * 400) + 'ремонт офиса'
        hits = self.service.search([self.document], 'ремонт', 0.5)
        self.assertIn('ремонт офиса', hits[0]['snippet'])
        self.assertIn('ремонт офиса', split_text(self.document['normalized_text'])[-1])

    def test_absent_model_produces_explicit_error(self):
        service = SemanticSearch(self.database, self.directory.name)
        with patch('contracts.search.load_model', side_effect=FileNotFoundError):
            with self.assertRaises(SearchUnavailable):
                service.search([self.document], 'ремонт')


class DocumentsPageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'tests',
                               'DATABASE': str(root / 'data.sqlite3'),
                               'UPLOAD_FOLDER': str(root / 'uploads'), 'DOCUMENTS_PAGE_SIZE': 2})
        self.client = self.app.test_client()
        for index, amount in enumerate(['9.50', '100.05', '900.50'], 1):
            fields = {'number': f'NO-{index}', 'date': f'2026-0{index}-01',
                      'amount': amount, 'customer': f'Заказчик {index}', 'contractor': f'Исполнитель {index}'}
            storage.save_document(self.app.config['DATABASE'], f'{index}.docx', f'{index}.docx',
                                  Result('текст', 'текст', fields, []))

    def tearDown(self):
        self.directory.cleanup()

    def test_new_page_sort_pagination_links_and_home_navigation(self):
        response = self.client.get('/documents?sort=amount&direction=asc')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertLess(html.index('NO-1'), html.index('NO-2'))
        self.assertNotIn('NO-3', html)
        self.assertIn('sort=amount', html)
        self.assertIn('direction=asc', html)
        self.assertIn('page=2', html)
        last_page = self.client.get('/documents?sort=amount&direction=asc&page=2').get_data(as_text=True)
        self.assertIn('NO-3', last_page)
        self.assertIn('href="/documents"', self.client.get('/').get_data(as_text=True))

    def test_semantic_results_can_be_sorted_and_query_is_preserved(self):
        hits = [dict(item, score=0.9 - index / 10, snippet='обучение персонала') for index, item in
                enumerate(storage.list_documents(self.app.config['DATABASE']))]
        self.app.extensions['semantic_search'] = Mock(search=Mock(return_value=hits))
        response = self.client.get('/documents', query_string={'q': 'развитие навыков', 'sort': 'amount', 'direction': 'asc'})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertLess(html.index('NO-1'), html.index('NO-2'))
        self.assertIn('развитие навыков', html)
        self.assertIn('обучение персонала', html)
        self.assertIn('Сходство', html)
        self.app.extensions['semantic_search'].search.assert_called_once()

    def test_no_hits_and_missing_model_are_different_states(self):
        search = Mock(search=Mock(return_value=[]))
        self.app.extensions['semantic_search'] = search
        response = self.client.get('/documents?q=рыбки')
        self.assertEqual(response.status_code, 200)
        self.assertIn('не найдены', response.get_data(as_text=True))
        search.search.side_effect = SearchUnavailable('Поиск недоступен')
        with self.assertLogs(self.app.logger, level='WARNING'):
            response = self.client.get('/documents?q=рыбки')
        self.assertEqual(response.status_code, 503)
        self.assertIn('Поиск недоступен', response.get_data(as_text=True))
        self.assertEqual(self.client.get('/documents?sort=date').status_code, 200)

    def test_invalid_options_and_query_limit(self):
        for url in ['/documents?sort=sql', '/documents?direction=wrong', '/documents?page=hello', '/documents?q=' + 'x' * 501]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get('/documents?q=%20%20&sort=relevance').status_code, 200)

    def test_untrusted_text_is_escaped(self):
        hit = dict(storage.get_document(self.app.config['DATABASE'], 1), score=0.9, snippet='<img src=x onerror=alert(1)>')
        self.app.extensions['semantic_search'] = Mock(search=Mock(return_value=[hit]))
        html = self.client.get('/documents', query_string={'q': '<b>query</b>'}).get_data(as_text=True)
        self.assertIn('&lt;img', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;b&gt;query&lt;/b&gt;', html)
