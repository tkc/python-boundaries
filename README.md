# Python Architecture Boundaries

このGitHub Actionは、Pythonプロジェクトのアーキテクチャ境界を強制するためのツールです。レイヤードアーキテクチャやクリーンアーキテクチャなど、層状の依存関係ルールを持つプロジェクトで特に役立ちます。

## 特徴

- アーキテクチャ要素（層）とそれらの間の依存関係ルールを定義できます
- カスタム設定ファイルをサポート（YAML, TOML）
- GitHub Actionsの注釈機能による分かりやすいエラー表示
- どのリポジトリからでも直接使用可能

## 使い方

### 基本的な使用方法

```yaml
name: Python Checks

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  architecture-check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Check architecture boundaries
      uses: tkc/python-boundaries@v1
```

### カスタム設定ファイルの使用

プロジェクトのルートに `.boundaries.yml` ファイルを作成:

```yaml
elements:
  - type: "domain"
    pattern: "src/domain/.*\\.py$"
  - type: "application"
    pattern: "src/application/.*\\.py$"
  - type: "infrastructure"
    pattern: "src/infrastructure/.*\\.py$"
  - type: "presentation"
    pattern: "src/presentation/.*\\.py$"

rules:
  default: "disallow"
  specific:
    - from: "presentation"
      allow: ["application", "domain"]
    - from: "application"
      allow: ["domain"]
    - from: "infrastructure"
      allow: ["domain", "application"]
```

### PRでエラーを表示するが失敗させない

```yaml
- name: Check architecture boundaries
  uses: tkc/python-boundaries@v1
  with:
    fail-on-error: false
```

### 結果に基づいて条件分岐

```yaml
- name: Check architecture boundaries
  id: boundaries
  uses: tkc/python-boundaries@v1
  with:
    fail-on-error: false

- name: Post violation summary
  if: steps.boundaries.outputs.has-violations == 'true'
  run: |
    echo "アーキテクチャ境界違反が ${steps.boundaries.outputs.violation-count} 件見つかりました"
```

## 設定オプション

### elements

アーキテクチャの要素（層）を定義します。各要素には以下のプロパティがあります：

- `type`: 要素の種類（例: "domain", "application"）
- `pattern`: ファイルパスを識別するための正規表現パターン

### rules

依存関係のルールを定義します：

- `default`: デフォルトの依存関係ポリシー（"allow" または "disallow"）
- `specific`: 特定の要素間の依存関係ルール
  - `from`: ソース要素のタイプ
  - `allow`: 依存を許可する要素のタイプ（リスト）
  - `disallow`: 依存を禁止する要素のタイプ（リスト）

## 設定ファイル

以下の形式の設定ファイルがサポートされています:

- `.boundaries.yml` または `.boundaries.yaml`
- `.boundaries.toml`
- `ruff.toml` (boundariesセクション)
- `pyproject.toml` (tool.ruff.boundariesセクション)

## アクションパラメータ

| 入力 | 説明 | 必須 | デフォルト |
|------|------|------|----------|
| path | チェックするパス | いいえ | . |
| config | カスタム設定ファイルへのパス | いいえ | "" |
| fail-on-error | 違反が見つかった場合にアクションを失敗させるか | いいえ | true |

## 出力

| 出力 | 説明 |
|------|------|
| has-violations | 違反が見つかったかどうか (true/false) |
| violation-count | 見つかった違反の数 |

## クリーンアーキテクチャの例

```yaml
elements:
  - type: "entities"
    pattern: "src/domain/entities/.*\\.py$"
  - type: "usecases"
    pattern: "src/domain/usecases/.*\\.py$"
  - type: "controllers"
    pattern: "src/adapters/controllers/.*\\.py$"
  - type: "presenters"
    pattern: "src/adapters/presenters/.*\\.py$"
  - type: "repositories"
    pattern: "src/adapters/repositories/.*\\.py$"
  - type: "frameworks"
    pattern: "src/frameworks/.*\\.py$"

rules:
  default: "disallow"
  specific:
    - from: "entities"
      allow: []
    - from: "usecases"
      allow: ["entities"]
    - from: "controllers" 
      allow: ["usecases", "entities"]
    - from: "presenters"
      allow: ["entities"]
    - from: "repositories"
      allow: ["entities"]
    - from: "frameworks"
      allow: ["controllers", "presenters", "repositories"]
```

## ライセンス

MIT
