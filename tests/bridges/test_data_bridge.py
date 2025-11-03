import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data_bridge import Data, DataStub, UserStatistics, Remindme, AutoUpdate


class TestDataStub(unittest.TestCase):
    def test_singleton_creates_instance(self):
        stub1 = DataStub.singleton()
        stub2 = DataStub.singleton()
        self.assertIs(stub1, stub2)

    def test_singleton_runtime_error(self):
        with self.assertRaises(RuntimeError):
            DataStub()

    def test_yolo_query_returns_empty(self):
        stub = DataStub.singleton()
        self.assertEqual(stub.yolo_query("SELECT * FROM test"), "")

    def test_get_db_tables_returns_zero(self):
        stub = DataStub.singleton()
        self.assertEqual(stub.get_db_tables(), 0)

    def test_read_all_user_statistics_returns_empty(self):
        stub = DataStub.singleton()
        self.assertEqual(stub.read_all_user_statistics(), [])

    def test_read_user_statistics_returns_none(self):
        stub = DataStub.singleton()
        self.assertIsNone(stub.read_user_statistics("test_user"))

    def test_increment_methods_do_nothing(self):
        stub = DataStub.singleton()
        stub.increment_user_statistics_commands_used("test")
        stub.increment_user_statistics_thanks_given("test")

    def test_alias_methods(self):
        stub = DataStub.singleton()
        stub.add_alias("long", "short")
        stub.remove_alias("long")
        self.assertEqual(stub.read_all_aliases(), {})

    def test_auto_update_methods(self):
        stub = DataStub.singleton()
        self.assertIsNone(stub.read_auto_update_from_id(1))
        self.assertIsNone(stub.read_auto_update_from_reddit_thread("url"))
        self.assertEqual(stub.read_all_auto_updates(), [])

        auto_update = stub.write_auto_update("reddit_url", "liqui_url", "swiss", "none", 1)
        self.assertIsInstance(auto_update, AutoUpdate)
        self.assertEqual(auto_update.auto_update_id, -1)

        stub.delete_auto_update(auto_update)

    def test_remindme_methods(self):
        stub = DataStub.singleton()
        self.assertEqual(stub.read_remindmes(), [])

        remindme = stub.write_remindme("user", "message", 3600, 12345)
        self.assertIsInstance(remindme, Remindme)
        self.assertEqual(remindme.remindme_id, -1)

        stub.delete_remindme(1)

    def test_scheduled_post_methods(self):
        stub = DataStub.singleton()
        stub.write_already_warned_scheduled_post(1, int(time.time()))
        self.assertEqual(stub.read_already_warned_scheduled_posts(0), [])

        stub.write_already_warned_confirmed_post(1, int(time.time()))
        self.assertEqual(stub.read_already_confirmed_scheduled_posts(0), [])

    def test_logs_methods(self):
        stub = DataStub.singleton()
        stub.write_to_logs([(datetime.now(), "test log")])
        self.assertEqual(stub.read_logs(10), [])

    def test_triflair_methods(self):
        stub = DataStub.singleton()
        stub.add_triflair("test_flair")
        self.assertEqual(stub.read_triflairs(), [])
        stub.yeet_triflair("test_flair")


class TestData(unittest.TestCase):
    def setUp(self):
        # Patch rleb_secrets for all tests to avoid AttributeError in CI
        # In CI, rleb_secrets is a dict, not a module, so accessing .DATA_MODE fails
        self.secrets_patcher = patch("data_bridge.rleb_secrets")
        self.mock_secrets = self.secrets_patcher.start()
        self.mock_secrets.DATA_MODE = "real"
        self.mock_secrets.DB_NAME = "test_db"
        self.mock_secrets.DB_HOST = "test_host"
        self.mock_secrets.DB_USER = "test_user"
        self.mock_secrets.DB_PORT = "5432"
        self.mock_secrets.DB_PASSWORD = "test_pass"

    def tearDown(self):
        self.secrets_patcher.stop()

    @patch.dict(os.environ, {"DATA_MODE": "stubbed"})
    def test_singleton_returns_data_stub_when_stubbed(self):
        self.mock_secrets.DATA_MODE = "stubbed"
        Data._singleton = None
        instance = Data.singleton()
        self.assertIsInstance(instance, DataStub)

    def test_singleton_runtime_error(self):
        with self.assertRaises(RuntimeError):
            Data()

    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_singleton_returns_data_when_real(self):
        self.mock_secrets.DATA_MODE = "real"
        Data._singleton = None
        instance = Data.singleton()
        self.assertIsInstance(instance, Data)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real", "DB_NAME": "test", "DB_HOST": "localhost", "DB_USER": "user", "DB_PORT": "5432", "DB_PASSWORD": "pass"})
    def test_postgres_connection_uses_env_vars(self, mock_connect):
        Data._singleton = None
        data = Data.singleton()
        data.postgres_connection()
        mock_connect.assert_called_once_with(
            dbname="test",
            host="localhost",
            user="user",
            port="5432",
            password="pass"
        )

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_postgres_connection_uses_env_or_secrets(self, mock_connect):
        # This test works in both environments:
        # - CI: uses env vars set in workflow
        # - Local: uses rleb_secrets if env vars not set
        Data._singleton = None
        data = Data.singleton()
        data.postgres_connection()

        # Just verify it was called, don't care about specific values
        # since they differ between local (rleb_secrets) and CI (env vars)
        mock_connect.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_yolo_query_executes_sql(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("result1",), ("result2",)]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        result = data.yolo_query("SELECT * FROM test")

        self.assertIn("result1", result)
        self.assertIn("result2", result)
        # Verify both the read-only transaction and the actual query were executed
        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_cursor.execute.assert_any_call("SET TRANSACTION READ ONLY;")
        mock_cursor.execute.assert_any_call("SELECT * FROM test")

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_yolo_query_blocks_dangerous_commands(self, mock_connect):
        Data._singleton = None
        data = Data.singleton()

        dangerous_queries = [
            # Basic write operations
            "INSERT INTO test VALUES (1)",
            "UPDATE test SET col=1",
            "DELETE FROM test",
            "DROP TABLE test",
            "CREATE TABLE test (id int)",
            "ALTER TABLE test ADD col int",
            "TRUNCATE TABLE test",
            "GRANT ALL ON test TO user",
            "REVOKE ALL ON test FROM user",
            "EXECUTE my_procedure()",
            "CALL my_procedure()",
            "COPY test FROM '/file'",
            # Esoteric commands
            "DO $$ BEGIN RAISE NOTICE 'test'; END $$",
            "LOAD '/path/to/library'",
            "VACUUM test",
            "LOCK TABLE test",
            "SET search_path TO public",
            "PREPARE stmt AS SELECT 1",
            "REFRESH MATERIALIZED VIEW mv",
            "REINDEX TABLE test",
            "CLUSTER test USING idx",
            "ANALYZE test",
            "COMMENT ON TABLE test IS 'comment'",
            "CHECKPOINT",
            "DISCARD ALL",
            "IMPORT FOREIGN SCHEMA s FROM SERVER srv INTO public",
            "LISTEN channel",
            "UNLISTEN channel",
            "NOTIFY channel",
        ]

        for query in dangerous_queries:
            with self.assertRaises(ValueError) as context:
                data.yolo_query(query)
            self.assertIn("is not allowed", str(context.exception))

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_get_db_tables_returns_count(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (5,)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        count = data.get_db_tables()

        self.assertEqual(count, 5)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_all_user_statistics(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("user1", 10, 5), ("user2", 20, 10)]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        stats = data.read_all_user_statistics()

        self.assertEqual(len(stats), 2)
        self.assertIsInstance(stats[0], UserStatistics)
        self.assertEqual(stats[0].discord_username, "user1")

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_all_user_statistics_uses_cache(self, mock_connect):
        Data._singleton = None
        Data._cache = {"user_statistics": [UserStatistics("cached", 1, 1)]}
        data = Data.singleton()
        stats = data.read_all_user_statistics()

        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].discord_username, "cached")
        mock_connect.assert_not_called()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_user_statistics_not_found(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        stat = data.read_user_statistics("nonexistent")

        self.assertIsNone(stat)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_user_statistics_found(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ("user1", 10, 5)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        stat = data.read_user_statistics("user1")

        self.assertIsInstance(stat, UserStatistics)
        self.assertEqual(stat.discord_username, "user1")
        self.assertEqual(stat.commands_used, 10)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_increment_user_statistics_commands_used(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {"user_statistics": [], "user_statistics_test": Mock()}
        data = Data.singleton()
        data.increment_user_statistics_commands_used("test")

        self.assertNotIn("user_statistics", Data._cache)
        self.assertNotIn("user_statistics_test", Data._cache)
        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_increment_user_statistics_thanks_given(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        data.increment_user_statistics_thanks_given("test")

        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_add_alias(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {"aliases": {}}
        data = Data.singleton()
        data.add_alias("long_name", "short")

        self.assertNotIn("aliases", Data._cache)
        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_remove_alias(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        data.remove_alias("long_name")

        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_all_aliases(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("long1", "short1"), ("long2", "short2")]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        aliases = data.read_all_aliases()

        self.assertEqual(len(aliases), 2)
        self.assertEqual(aliases["long1"], "short1")
        self.assertIn("aliases", Data._cache)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_auto_update_from_id_found(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1, "reddit_url", "liqui_url", "swiss", "none", 12345, 1)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        auto_update = data.read_auto_update_from_id(1)

        self.assertIsInstance(auto_update, AutoUpdate)
        self.assertEqual(auto_update.auto_update_id, 1)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_auto_update_from_id_not_found(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        auto_update = data.read_auto_update_from_id(999)

        self.assertIsNone(auto_update)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_auto_update_from_reddit_thread(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1, "reddit_url", "liqui_url", "swiss", "none", 12345, 1)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        auto_update = data.read_auto_update_from_reddit_thread("reddit_url")

        self.assertIsInstance(auto_update, AutoUpdate)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_all_auto_updates(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, "url1", "liqui1", "swiss", "none", 12345, 1),
            (2, "url2", "liqui2", "bracket", "none", 12346, 2)
        ]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        auto_updates = data.read_all_auto_updates()

        self.assertEqual(len(auto_updates), 2)
        self.assertIsInstance(auto_updates[0], AutoUpdate)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_delete_auto_update(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        auto_update = AutoUpdate(1, "url", "liqui", "swiss", "none", 12345, 1)
        data.delete_auto_update(auto_update)

        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch("data_bridge.datetime")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_write_auto_update(self, mock_datetime, mock_connect):
        mock_datetime.now.return_value.timestamp.return_value = 12345.0
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (99,)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        auto_update = data.write_auto_update("reddit_url", "liqui_url#anchor", "swiss", "none", 1)

        self.assertIsInstance(auto_update, AutoUpdate)
        self.assertEqual(auto_update.auto_update_id, 99)
        self.assertEqual(auto_update.liquipedia_url, "liqui_url")

    @patch("data_bridge.psycopg2.connect")
    @patch("data_bridge.time.time")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_write_remindme(self, mock_time, mock_connect):
        mock_time.return_value = 1000.0
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (42,)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        remindme = data.write_remindme("user", "message", 3600, 12345)

        self.assertIsInstance(remindme, Remindme)
        self.assertEqual(remindme.remindme_id, 42)
        self.assertEqual(remindme.trigger_timestamp, 4600.0)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_delete_remindme(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        data.delete_remindme(1)

        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_remindmes(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, "user1", "msg1", 12345, 1500.0),
            (2, "user2", "msg2", 67890, 2000.0)
        ]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        remindmes = data.read_remindmes()

        self.assertEqual(len(remindmes), 2)
        self.assertIsInstance(remindmes[0], Remindme)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_write_already_warned_scheduled_post(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        data.write_already_warned_scheduled_post(1, 12345)

        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_already_warned_scheduled_posts(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        post_ids = data.read_already_warned_scheduled_posts(1000)

        self.assertEqual(post_ids, [1, 2, 3])

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_write_already_warned_confirmed_post(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        data.write_already_warned_confirmed_post(1, 12345)

        mock_cursor.execute.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_already_confirmed_scheduled_posts(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [(10,), (20,)]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        post_ids = data.read_already_confirmed_scheduled_posts(1000)

        self.assertEqual(post_ids, [10, 20])

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_write_to_logs(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        data.write_to_logs([(datetime.now(), "log1"), (datetime.now(), "log2")])

        mock_cursor.executemany.assert_called_once()

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_logs(self, mock_connect):
        now = datetime.now()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("log1", now), ("log2", now)]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        data = Data.singleton()
        logs = data.read_logs(10)

        self.assertEqual(len(logs), 2)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_add_triflair(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {"triflair": []}
        data = Data.singleton()
        data.add_triflair("test_flair")

        mock_cursor.execute.assert_called_once()
        self.assertNotIn("triflair", Data._cache)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_read_triflairs(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("flair1",), ("flair2",)]
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {}
        data = Data.singleton()
        flairs = data.read_triflairs()

        self.assertEqual(len(flairs), 2)

    @patch("data_bridge.psycopg2.connect")
    @patch.dict(os.environ, {"DATA_MODE": "real"})
    def test_yeet_triflair(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        Data._singleton = None
        Data._cache = {"triflair": []}
        data = Data.singleton()
        data.yeet_triflair("test_flair")

        mock_cursor.execute.assert_called_once()
        self.assertNotIn("triflair", Data._cache)


if __name__ == "__main__":
    unittest.main()
