"""
architecture boundariesのテスト
"""
import importlib.util  # Added for checking optional dependency
import os
import sys
import tempfile
import unittest
from pathlib import Path

# モジュールのインポートパスを設定
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from run_checks import (
    check_file,
    default_config,
    determine_element_type,
    extract_imports,
    # identify_module_type, # No longer used directly
    is_allowed_dependency,
    load_config,
)


class TestElementType(unittest.TestCase):
    """要素タイプの判定に関するテスト"""

    def test_determine_element_type(self):
        """ファイルパスから要素タイプを判定するテスト"""
        elements = [
            {"type": "data", "pattern": ".*/data/.*\\.py$"},
            {"type": "logic", "pattern": ".*/logic/.*\\.py$"},
            {"type": "ui", "pattern": ".*/ui/.*\\.py$"}
        ]

        # 正常なパターン
        self.assertEqual(determine_element_type("app/data/models.py", elements), "data")
        self.assertEqual(determine_element_type("src/logic/services.py", elements), "logic")
        self.assertEqual(determine_element_type("project/ui/components.py", elements), "ui")

        # マッチしないパス
        self.assertIsNone(determine_element_type("app/other/file.py", elements))
        self.assertIsNone(determine_element_type("app/data/models.js", elements))

        # 空のパターン
        elements_with_empty = elements + [{"type": "empty", "pattern": ""}]
        self.assertEqual(determine_element_type("app/data/models.py", elements_with_empty), "data")

    # Removed test_identify_module_type as the function is no longer used directly
    # in the core checking logic of run_checks.py. The functionality is implicitly
    # tested via test_check_file.


class TestDependencyRules(unittest.TestCase):
    """依存関係ルールに関するテスト"""

    def test_is_allowed_dependency(self):
        """依存関係が許可されているかのテスト"""
        rules = {
            "default": "disallow",
            "specific": [
                {"from": "ui", "allow": ["logic", "data"]},
                {"from": "logic", "allow": ["data"]},
                {"from": "special", "disallow": ["ui"]}
            ]
        }

        # 許可された依存関係
        self.assertTrue(is_allowed_dependency("ui", "logic", rules))
        self.assertTrue(is_allowed_dependency("ui", "data", rules))
        self.assertTrue(is_allowed_dependency("logic", "data", rules))

        # 禁止された依存関係
        self.assertFalse(is_allowed_dependency("data", "logic", rules))
        self.assertFalse(is_allowed_dependency("data", "ui", rules))
        self.assertFalse(is_allowed_dependency("logic", "ui", rules))

        # disallowの指定
        self.assertFalse(is_allowed_dependency("special", "ui", rules))
        self.assertFalse(is_allowed_dependency("special", "logic", rules))  # デフォルトルールで禁止

        # 自分自身への依存は常に許可
        self.assertTrue(is_allowed_dependency("data", "data", rules))
        self.assertTrue(is_allowed_dependency("logic", "logic", rules))
        self.assertTrue(is_allowed_dependency("ui", "ui", rules))

    def test_default_allow(self):
        """デフォルトが許可の場合のテスト"""
        rules = {
            "default": "allow",
            "specific": [
                {"from": "data", "disallow": ["ui"]},
            ]
        }

        # 明示的に禁止された依存関係
        self.assertFalse(is_allowed_dependency("data", "ui", rules))

        # デフォルトで許可される依存関係
        self.assertTrue(is_allowed_dependency("data", "logic", rules))
        self.assertTrue(is_allowed_dependency("logic", "ui", rules))


class TestConfigHandling(unittest.TestCase):
    """設定ファイル処理に関するテスト"""

    def test_default_config(self):
        """デフォルト設定の内容確認"""
        config = default_config()

        self.assertIn("elements", config)
        self.assertIn("rules", config)
        self.assertEqual(len(config["elements"]), 3)  # data, logic, ui
        self.assertEqual(config["rules"]["default"], "disallow")
        self.assertEqual(len(config["rules"]["specific"]), 2)  # ui->logic/data, logic->data

    def test_load_config_from_yml(self):
        """YAMLファイルからの設定読み込みテスト"""
        # Check if pyyaml is available before attempting to import and use it
        if importlib.util.find_spec("yaml") is None:
            self.skipTest("pyyamlがインストールされていません")

        # pyyaml is available, proceed with the test
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, ".boundaries.yml")
            with open(config_path, "w") as f:
                    # Use single quotes for pattern to avoid YAML escape issues with backslash
                    f.write("""
elements:
  - type: "domain"
    pattern: 'src/domain/.*\\.py$'
  - type: "application"
    pattern: 'src/application/.*\\.py$'

rules:
  default: "disallow"
  specific:
    - from: "application"
      allow: ["domain"]
""")

            config = load_config(Path(tmpdir))

            self.assertIn("elements", config)
            self.assertEqual(len(config["elements"]), 2)
            self.assertEqual(config["elements"][0]["type"], "domain")
            self.assertEqual(config["rules"]["specific"][0]["from"], "application")
            self.assertEqual(config["rules"]["specific"][0]["allow"], ["domain"])
        # No need for except ImportError as we check availability first


class TestFilesystemInteraction(unittest.TestCase):
    """ファイルシステム操作に関するテスト"""

    def test_check_file(self):
        """ファイルの依存関係チェックテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, "app", "data")
            logic_dir = os.path.join(tmpdir, "app", "logic")
            os.makedirs(data_dir)
            os.makedirs(logic_dir)

            # データモデル
            models_path = os.path.join(data_dir, "models.py")
            with open(models_path, "w") as f:
                f.write('class User:\n    def __init__(self, name):\n        self.name = name\n')

            # サービス（正当な依存）
            services_path = os.path.join(logic_dir, "services.py")
            with open(services_path, "w") as f:
                f.write('from app.data.models import User\n\nclass UserService:\n    def get_user(self, user_id):\n        return User("Test")\n')

            # 不正な依存
            invalid_path = os.path.join(data_dir, "invalid.py")
            with open(invalid_path, "w") as f:
                f.write('from app.logic.services import UserService\n\nclass InvalidModel:\n    def __init__(self):\n        self.service = UserService()\n')

            # 要素タイプの定義
            elements = [
                {"type": "data", "pattern": "app/data/.*\\.py$"},
                {"type": "logic", "pattern": "app/logic/.*\\.py$"}
            ]

            # 設定
            config = {
                "elements": elements,
                "rules": {
                    "default": "disallow",
                    "specific": [
                        {"from": "logic", "allow": ["data"]}
                    ]
                }
            }

            # デバッグ: パターンが正しく動作しているか確認
            self.assertEqual(determine_element_type(invalid_path, elements), "data")

            # デバッグ: インポート抽出のテスト
            imports = extract_imports(invalid_path)
            self.assertEqual(len(imports), 1)
            self.assertEqual(imports[0][1], "app.logic.services")

            # デバッグ: モジュールタイプ判定 (identify_module_type is removed)
            # self.assertEqual(identify_module_type("app.data.models", elements), "data")
            # self.assertEqual(identify_module_type("app.logic.services", elements), "logic")

            # 違反チェック
            violations = check_file(invalid_path, config)

            # 違反検出の確認
            self.assertEqual(len(violations), 1, f"データ層からロジック層への依存違反が検出されるべき (実際の違反数: {len(violations)})")

            if len(violations) > 0:
                _, from_type, to_type, import_name = violations[0]
                self.assertEqual(from_type, "data")
                self.assertEqual(to_type, "logic")
                self.assertEqual(import_name, "app.logic.services")


if __name__ == '__main__':
    unittest.main()
