#!/usr/bin/env python
"""
GitHub Actions用アーキテクチャ境界チェックスクリプト
"""
import os
import sys
import re
import ast
import json
import argparse
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set

# 依存ライブラリを動的に確認・インポート
def import_optional_dependency(name):
    """依存ライブラリが利用可能かを確認してインポート"""
    if importlib.util.find_spec(name) is not None:
        return importlib.import_module(name)
    return None

yaml = import_optional_dependency("yaml")
tomli = import_optional_dependency("tomli")

def load_config(repo_root: Path, config_path: str = "") -> Dict[str, Any]:
    """設定ファイルを読み込む"""
    # 指定された設定ファイルがあれば優先
    if config_path and os.path.exists(config_path):
        config_file = Path(config_path)
    else:
        # 優先順位: .boundaries.yml > .boundaries.toml > ruff.toml > pyproject.toml
        config_paths = [
            repo_root / ".boundaries.yml",
            repo_root / ".boundaries.yaml",
            repo_root / ".boundaries.toml",
            repo_root / "ruff.toml",
            repo_root / "pyproject.toml"
        ]
        
        config_file = None
        for path in config_paths:
            if path.exists():
                config_file = path
                break
        
        if not config_file:
            print("::warning::設定ファイルが見つかりません。デフォルト設定を使用します。")
            return default_config()
    
    try:
        # ファイル形式に応じて読み込み
        if config_file.suffix in ['.yml', '.yaml']:
            if yaml is None:
                print("::warning::pyyamlがインストールされていません。デフォルト設定を使用します。")
                return default_config()
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config if config else default_config()
                
        elif config_file.suffix == '.toml':
            if tomli is None:
                print("::warning::tomliがインストールされていません。デフォルト設定を使用します。")
                return default_config()
            with open(config_file, 'rb') as f:
                toml_data = tomli.load(f)
                # pyproject.tomlの場合
                if config_file.name == "pyproject.toml":
                    if "tool" in toml_data and "ruff" in toml_data["tool"]:
                        if "boundaries" in toml_data["tool"]["ruff"]:
                            return toml_data["tool"]["ruff"]["boundaries"]
                    if "tool" in toml_data and "boundaries" in toml_data["tool"]:
                        return toml_data["tool"]["boundaries"]
                # ruff.tomlの場合
                elif "boundaries" in toml_data:
                    return toml_data["boundaries"]
    except Exception as e:
        print(f"::warning::設定ファイルの読み込みに失敗しました: {e}。デフォルト設定を使用します。")
    
    # 読み込みに失敗したらデフォルト
    return default_config()

def default_config() -> Dict[str, Any]:
    """デフォルト設定"""
    return {
        "elements": [
            {"type": "data", "pattern": ".*/data/.*\\.py$"},
            {"type": "logic", "pattern": ".*/logic/.*\\.py$"},
            {"type": "ui", "pattern": ".*/ui/.*\\.py$"}
        ],
        "rules": {
            "default": "disallow",
            "specific": [
                {"from": "ui", "allow": ["logic", "data"]},
                {"from": "logic", "allow": ["data"]}
            ]
        }
    }

def determine_element_type(file_path: str, elements: List[Dict[str, str]]) -> Optional[str]:
    """ファイルの要素タイプを判定"""
    for element in elements:
        pattern = element.get("pattern", "")
        if not pattern:
            continue
            
        try:
            if re.search(pattern, file_path):
                return element.get("type")
        except re.error as e:
            print(f"::warning::正規表現エラー ({pattern}): {e}")
    
    return None

def is_allowed_dependency(from_type: str, to_type: str, rules: Dict) -> bool:
    """依存関係が許可されているかチェック"""
    # 自分自身への依存は常に許可
    if from_type == to_type:
        return True
        
    default_allow = rules.get("default", "disallow") == "allow"
    specific_rules = rules.get("specific", [])
    
    # 特定のルールを確認
    for rule in specific_rules:
        if rule.get("from") == from_type:
            if "allow" in rule and to_type in rule.get("allow", []):
                return True
            if "disallow" in rule and to_type in rule.get("disallow", []):
                return False
    
    # デフォルトに従う
    return default_allow

def extract_imports(file_path: str) -> List[Tuple[int, str]]:
    """ファイルからインポート文を抽出"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append((node.lineno, name.name))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append((node.lineno, node.module))
        except SyntaxError as e:
            print(f"::warning file={file_path}::構文エラー: {e}")
            
        return imports
    except Exception as e:
        print(f"::warning file={file_path}::ファイル読み込みエラー: {e}")
        return []

def identify_module_type(import_name: str, elements: List[Dict]) -> Optional[str]:
    """インポートモジュールのタイプを特定（改善版）"""
    module_parts = import_name.split('.')
    best_match_type = None
    max_match_len = 0

    for element in elements:
        element_type = element.get("type", "")
        pattern = element.get("pattern", "")
        if not pattern:
            continue

        # パターンからパス構造のキーワードを抽出
        # 例: "app/data/.*\\.py$" -> ["app", "data"]
        key_parts = []
        for part in pattern.split('/'):
            cleaned_part = re.sub(r'(\.\*|\\|\.py\$|\$)', '', part) # 正規表現メタ文字を除去
            if cleaned_part and cleaned_part != '*':
                key_parts.append(cleaned_part)

        # モジュール名がパターンキーワードで始まっているか確認
        # より長く一致するパターンを優先する
        match_len = 0
        match = True
        if len(key_parts) <= len(module_parts):
            for i, key_part in enumerate(key_parts):
                if module_parts[i] == key_part:
                    match_len += 1
                else:
                    match = False
                    break
            if match and match_len > max_match_len:
                 max_match_len = match_len
                 best_match_type = element_type
        # 完全一致ではなく前方一致で判定する場合 (より緩いマッチング)
        # import_path_prefix = ".".join(key_parts)
        # if import_name.startswith(import_path_prefix):
        #     # より長く一致するパターンを優先
        #     if len(import_path_prefix) > max_match_len:
        #         max_match_len = len(import_path_prefix)
        #         best_match_type = element_type

    return best_match_type

def _import_name_to_pseudo_path(import_name: str) -> str:
    """インポート名を簡易的なファイルパスに変換 (例: app.logic.services -> app/logic/services.py)"""
    # TODO: より堅牢なインポート解決が必要
    return import_name.replace('.', '/') + ".py"

def check_file(file_path: str, config: Dict) -> List[Tuple[int, str, str, str]]:
    """ファイルの境界違反をチェック"""
    # ファイルの要素タイプを判定
    file_type = determine_element_type(file_path, config.get("elements", []))
    if not file_type:
        return []  # 監視対象外のファイル
    
    # インポートを抽出
    imports = extract_imports(file_path)
    violations = []
    
    for line_num, import_name in imports:
        # インポートの要素タイプを判定 (determine_element_typeを使用)
        pseudo_path = _import_name_to_pseudo_path(import_name)
        import_type = determine_element_type(pseudo_path, config.get("elements", []))

        if import_type and import_type != file_type:
            # 依存関係のチェック
            if not is_allowed_dependency(file_type, import_type, config.get("rules", {})):
                violations.append((
                    line_num,
                    file_type,
                    import_type,
                    import_name
                ))
    
    return violations

def scan_python_files(directory: Path) -> List[Path]:
    """Pythonファイルを再帰的に検索"""
    python_files = []
    try:
        # 単一ファイルの場合
        if directory.is_file() and directory.suffix == '.py':
            return [directory]
            
        # ディレクトリの場合は再帰的に検索
        for item in directory.glob('**/*.py'):
            if item.is_file():
                python_files.append(item)
    except Exception as e:
        print(f"::warning::ファイル検索エラー: {e}")
    return python_files

def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(description='Pythonプロジェクトのアーキテクチャ境界をチェック')
    parser.add_argument('path', nargs='?', default='.', help='チェックするパス（デフォルト: カレントディレクトリ）')
    parser.add_argument('config', nargs='?', default='', help='設定ファイルのパス（デフォルト: 自動検出）')
    parser.add_argument('--no-fail', action='store_true', help='違反があっても終了コード0で終了')
    return parser.parse_args()

def main():
    """メイン関数"""
    try:
        # コマンドライン引数を解析
        args = parse_args()
        check_path = args.path
        config_path = args.config
        no_fail = args.no_fail
        
        repo_root = Path(check_path)
        if not repo_root.exists():
            print(f"::error::指定されたパス '{check_path}' が存在しません。")
            sys.exit(1)
        
        # 単一ファイルの場合はディレクトリを取得
        if repo_root.is_file():
            repo_parent = repo_root.parent
        else:
            repo_parent = repo_root
        
        # 設定を読み込む
        config = load_config(repo_parent, config_path)
        
        print(f"設定を読み込みました:")
        print(f"  要素数: {len(config.get('elements', []))}")
        print(f"  デフォルトルール: {config.get('rules', {}).get('default', 'disallow')}")
        
        violations_found = False
        all_violations = []
        
        # Pythonファイルを再帰的に検索
        python_files = scan_python_files(repo_root)
        print(f"検出されたPythonファイル数: {len(python_files)}")
        
        for file_path in python_files:
            rel_path = os.path.relpath(file_path, repo_parent)
            
            # GitHubActionsの出力グループを開始
            print(f"::group::チェック中: {rel_path}")
            
            violations = check_file(str(file_path), config)
            if violations:
                violations_found = True
                all_violations.extend([(rel_path, *v) for v in violations])
                for line_num, from_type, to_type, import_name in violations:
                    # GitHubActionsのアノテーション形式でエラーを出力
                    print(f"::error file={rel_path},line={line_num}::{from_type}層が{to_type}層に依存しています（import {import_name}）")
            else:
                print("違反なし")
            
            # グループを終了
            print("::endgroup::")
        
        # 結果のサマリー
        print("\n==== チェック完了 ====")
        if violations_found:
            print(f"::error::合計 {len(all_violations)} 件のアーキテクチャ境界違反が見つかりました。")
            if not no_fail:
                sys.exit(1)
        else:
            print("::notice::アーキテクチャ境界違反は見つかりませんでした。👍")
    
    except Exception as e:
        print(f"::error::予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
