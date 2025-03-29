"""
python-boundariesの結合テスト
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# モジュールのインポートパスを設定
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestCommandLine(unittest.TestCase):
    """コマンドライン実行に関するテスト"""
    
    def setUp(self):
        """テスト環境のセットアップ"""
        # スクリプトへのパス
        self.script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'run_checks.py'))
        
        # テスト用のディレクトリ
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        
        # テスト用のファイル構造を作成
        os.makedirs(self.project_dir / "app" / "data")
        os.makedirs(self.project_dir / "app" / "logic")
        os.makedirs(self.project_dir / "app" / "ui")
        
        # 設定ファイル
        config_content = """
elements:
  - type: "data"
    pattern: "app/data/.*\\.py$"
  - type: "logic"
    pattern: "app/logic/.*\\.py$"
  - type: "ui"
    pattern: "app/ui/.*\\.py$"

rules:
  default: "disallow"
  specific:
    - from: "ui"
      allow: ["logic", "data"]
    - from: "logic"
      allow: ["data"]
"""
        with open(self.project_dir / ".boundaries.yml", "w") as f:
            f.write(config_content)
        
        # 通常のファイル
        with open(self.project_dir / "app" / "data" / "models.py", "w") as f:
            f.write("""
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
""")
        
        with open(self.project_dir / "app" / "logic" / "services.py", "w") as f:
            f.write("""
from app.data.models import User

class UserService:
    def get_user(self, user_id):
        return User("Test", "test@example.com")
""")
        
        with open(self.project_dir / "app" / "ui" / "views.py", "w") as f:
            f.write("""
from app.logic.services import UserService
from app.data.models import User

class UserView:
    def __init__(self):
        self.service = UserService()
    
    def display_user(self, user_id):
        user = self.service.get_user(user_id)
        return f"User: {user.name} ({user.email})"
""")
        
        # 違反を含むファイル
        with open(self.project_dir / "app" / "data" / "invalid.py", "w") as f:
            f.write("""
from app.logic.services import UserService  # 違反: データ層からロジック層への参照

class InvalidModel:
    def __init__(self):
        self.service = UserService()
""")
    
    def tearDown(self):
        """テスト環境のクリーンアップ"""
        self.temp_dir.cleanup()
    
    def test_no_violations(self):
        """違反がない場合のテスト"""
        # app/data/models.pyだけをチェック
        result = subprocess.run(
            [sys.executable, self.script_path, str(self.project_dir / "app" / "data" / "models.py")],
            capture_output=True,
            text=True
        )
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("違反なし", result.stdout)
        self.assertIn("違反は見つかりませんでした", result.stdout)
    
    def test_with_violations(self):
        """違反がある場合のテスト"""
        # app/data/invalid.pyだけをチェック
        result = subprocess.run(
            [sys.executable, self.script_path, str(self.project_dir / "app" / "data" / "invalid.py"), "--no-fail"],
            capture_output=True,
            text=True
        )
        
        self.assertEqual(result.returncode, 0)  # --no-failオプションでエラーコードは0
        self.assertIn("logic", result.stdout)
        self.assertIn("違反が見つかりました", result.stdout)
    
    def test_exit_code(self):
        """違反がある場合の終了コードテスト"""
        # --no-failオプションなしで実行
        result = subprocess.run(
            [sys.executable, self.script_path, str(self.project_dir / "app" / "data" / "invalid.py")],
            capture_output=True,
            text=True
        )
        
        self.assertNotEqual(result.returncode, 0)  # エラーコードは0以外
    
    def test_full_project(self):
        """プロジェクト全体のチェックテスト"""
        # プロジェクト全体をチェック
        result = subprocess.run(
            [sys.executable, self.script_path, str(self.project_dir), "--no-fail"],
            capture_output=True,
            text=True
        )
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("違反が見つかりました", result.stdout)
        # 正しい依存関係のファイルは違反がないことを確認
        self.assertNotIn("ui層がlogic層に依存しています", result.stdout)
        self.assertNotIn("ui層がdata層に依存しています", result.stdout)
        self.assertNotIn("logic層がdata層に依存しています", result.stdout)


if __name__ == "__main__":
    unittest.main()
