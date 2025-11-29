# WikiProject Lambda Application

Django + Aurora DSQL + AWS Cognito によるWikiアプリケーション

## アーキテクチャ

- **Framework**: Django 5.2
- **Database**: Aurora DSQL (本番), SQLite (ローカル開発)
- **Authentication**: AWS Cognito (JWT)
- **Deployment**: AWS Lambda + API Gateway (Mangum ASGI adapter)
- **Infrastructure**: AWS CDK

## 主な特徴

### Wiki機能

- **階層的なページ構造**: スラッシュ区切りのslugで階層化（例: `programming/python/basics`）
- **ツリー表示**: 自動生成される階層図（ナビゲーション＆ホームページ）
- **ページ共有**: 共有コードによるページ公開・編集権限管理
- **優先度管理**: 一括設定画面でページの優先度・公開設定を調整
- **公開/非公開**: 個人用メモと公開記事を分離管理
- **編集権限**: ページごとに他ユーザーの編集許可を設定可能

### Aurora DSQL対応

- UUID主キーを使用したカスタムUserモデル（SERIAL型回避）
- Django組み込みアプリ最小化（contenttypes依存なし）
- カスタムAnonymousUserクラス
- DSQL/非DSQLモードでの設定分離
- `db_constraint=False`による外部キー制約の明示的無効化

### 環境変数

- `USE_DSQL`: DSQLモードの有効化 (`true`/`false`)
- `USE_MOCK`: モックAWSサービスの使用 (`true`/`false`)
- `DEBUG`: Djangoデバッグモード (`true`/`false`)
- `SCRIPT_NAME`: API Gatewayステージ名（自動設定）

## データベースマイグレーション

### 前提条件

- Aurora DSQLクラスターが作成済み
- DSQLエンドポイントがSSM Parameter Storeに保存済み（`/DSQL/cluster_endpoint`）
- 適切なIAMロール/ポリシーが設定済み

### マイグレーション手順

#### 1. マイグレーションファイルの生成（ローカル環境）

```bash
cd /Users/hakira/Programs/WikiProject/WikiProject_App/Lambda

# モックSSMを使用したSQLite環境でマイグレーション生成
export USE_DSQL=false
export USE_MOCK=true
export DEBUG=true

# マイグレーションファイル生成
python manage.py makemigrations accounts
python manage.py makemigrations wiki
```

**重要**: マイグレーションファイルは**必ずGitにcommitする**必要があります。

- マイグレーションファイルはアプリケーションコードの一部
- Lambda環境でのデプロイ時にマイグレーションファイルが必要
- DSQLとSQLiteで同じマイグレーションファイルを使用可能（Djangoが各バックエンド用のSQLに自動変換）

```bash
# マイグレーションファイルをGitに追加
git add accounts/migrations/0001_initial.py
git add wiki/migrations/*.py
git commit -m "Add initial migrations for User and Wiki models"
```

#### 2. マイグレーションファイルの確認

```bash
# 生成されたマイグレーションファイルを確認
ls -la accounts/migrations/
ls -la wiki/migrations/

# マイグレーション内容の確認（データベース固有のSQLを表示）
python manage.py sqlmigrate accounts 0001
```

#### 3. Lambda経由でDSQLにマイグレーション適用

**推奨方法: Lambda直接呼び出し**

`lambda_function.py`に組み込まれたマイグレーション機能を使用：

```bash
# AWS CLIでLambda関数を直接呼び出し
aws lambda invoke \
  --function-name WikiProjectApp \
  --payload '{"action":"migrate"}' \
  response.json

# 結果を確認
cat response.json
```

または、AWS Lambda コンソールからテストイベントを作成して実行：

```json
{
  "action": "migrate"
}
```

**実装詳細**: `lambda_function.py`の`lambda_handler()`は`event.get('action') == 'migrate'`を検出すると、`run_migrations()`関数を実行してDjangoマイグレーションを適用します。API Gateway経由のリクエストには影響しません。

**その他の方法**

<details>
<summary>方法A: API経由でマイグレーション実行（要実装）</summary>

マイグレーション実行用のエンドポイントを追加：

```python
# WikiProject/urls.py に追加
from django.core.management import call_command
from django.http import JsonResponse
from io import StringIO

def run_migrations(request):
  """Run database migrations"""
  if not request.user.is_authenticated or not request.user.is_staff:
    return JsonResponse({'error': 'Unauthorized'}, status=403)

  output = StringIO()
  try:
    call_command('migrate', stdout=output, interactive=False)
    return JsonResponse({
      'status': 'success',
      'output': output.getvalue()
    })
  except Exception as e:
    return JsonResponse({
      'status': 'error',
      'message': str(e),
      'output': output.getvalue()
    }, status=500)

urlpatterns = [
  path('health/', health_check, name='health_check'),
  path('api/migrate/', run_migrations, name='run_migrations'),  # 追加
]
```

デプロイ後、エンドポイントを呼び出し：

```bash
# スタッフユーザーのCognito JWTトークンを取得して
curl -X POST https://wiki.h-akira.net/api/migrate/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```
</details>

<details>
<summary>方法B: AWS Systems Manager Session Manager経由</summary>

Lambda関数にSSM権限を付与し、Session Manager経由で直接実行：

```bash
# Lambda実行環境に接続（要追加設定）
aws ssm start-session --target <lambda-execution-environment>

# 環境変数設定
export USE_DSQL=true
export DJANGO_SETTINGS_MODULE=WikiProject.settings

# マイグレーション実行
python manage.py migrate
```

#### 4. マイグレーション状態の確認

```python
# WikiProject/urls.py に確認用エンドポイント追加
def migration_status(request):
  """Check migration status"""
  from django.db.migrations.executor import MigrationExecutor
  from django.db import connections, DEFAULT_DB_ALIAS

  executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
  targets = executor.loader.graph.leaf_nodes()
  plan = executor.migration_plan(targets)

  return JsonResponse({
    'pending_migrations': len(plan),
    'applied_migrations': len(executor.loader.applied_migrations),
    'details': [
      {'app': migration[0], 'name': migration[1]}
      for migration in plan
    ]
  })
```

### マイグレーション時の注意事項

1. **UUID主キー**: カスタムUserモデルはUUIDを主キーとして使用（DSQLのSERIAL型非対応のため）
2. **Django組み込みアプリ**: DSQLモードでは`django.contrib.admin`、`django.contrib.auth`などは使用不可
3. **トランザクション**: DSQLは楽観的同時実行制御を使用（デッドロックに注意）
4. **バックアップ**: 本番環境でのマイグレーション前にバックアップを推奨（ただしDSQLは自動バックアップ）
5. **マイグレーションの冪等性**: `python manage.py migrate`は何度実行しても安全（適用済みマイグレーションはスキップ）
6. **DSQL制約**: ALTER COLUMN操作は非対応のため、初期設計を慎重に行うこと

## ローカル開発環境

### SSMパラメータ管理

`manage.py`と`lambda_function.py`は起動時にSSM Parameter Storeからパラメータを取得し、環境変数に設定します。

**アーキテクチャ**:
- `lambda_function.py`: モジュールレベルでSSMパラメータ取得 → 環境変数設定 → Djangoインポート
- `manage.py`: `main()`関数でSSMパラメータ取得 → 環境変数設定 → Djangoインポート
- `settings.py`: 環境変数から設定を読み込み（SSMアクセスなし）

**モックモード** (`USE_MOCK=true`):
- `moto`を使用してAWSサービスをローカルでモック
- `mock/ssm.py`でモックSSMパラメータを設定
- 実際のAWS認証情報不要でローカル開発可能

### セットアップ

```bash
cd /Users/hakira/Programs/WikiProject/WikiProject_App/Lambda

# 仮想環境作成
python -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定（モックSSMを使用）
export USE_DSQL=false
export USE_MOCK=true
export DEBUG=true

# マイグレーション
python manage.py makemigrations
python manage.py migrate

# 開発サーバー起動
python manage.py runserver
```

**注意**: ローカル開発では`USE_MOCK=true`を推奨します。これにより、AWS認証情報なしで開発できます。

## デプロイ

AWS CodeBuildによる自動デプロイ：

```bash
# buildspec.ymlで定義
# - sam build
# - sam deploy
```

環境変数はSSM Parameter Storeから取得：
- `/Django/secret_key`
- `/Django/env/DEBUG`
- `/Cognito/user_pool_id`
- `/Cognito/client_id`
- `/Cognito/client_secret`
- `/DSQL/cluster_endpoint`

## プロジェクト構成

```
Lambda/
├── WikiProject/          # プロジェクト設定
│   ├── settings.py       # DSQL/非DSQL分離設定
│   ├── urls.py           # URLルーティング
│   ├── asgi.py           # ASGI設定
│   └── wsgi.py           # WSGI設定
├── accounts/             # 認証・ユーザー管理
│   ├── models.py         # カスタムUserモデル（UUID主キー）
│   ├── middleware.py     # Cognito JWT認証
│   ├── decorators.py     # 認証デコレータ
│   ├── views.py          # 認証API
│   └── urls.py           # 認証URLパターン
├── wiki/                 # Wikiアプリ
│   ├── models.py         # PageTable モデル
│   ├── views.py          # Wiki CRUD + 共有機能
│   ├── forms.py          # PageForm, PageSettingsFormSet
│   └── urls.py           # WikiURLパターン
├── lib/                  # カスタムライブラリ
│   └── tree/             # 階層構造ツリー生成
│       ├── __init__.py
│       └── tree.py       # Tree, gen_tree_htmls, gen_pages_ordered_by_tree
├── templates/            # テンプレート
│   ├── wiki/
│   │   ├── index.html
│   │   ├── detail.html
│   │   ├── edit.html
│   │   ├── page_settings.html
│   │   └── not_found.html
│   └── accounts/
│       ├── login.html
│       ├── signup.html
│       └── confirm.html
├── mock/                 # AWSモックデータ
│   └── ssm.py
├── static_local/         # 静的ファイル
├── lambda_function.py    # Lambda エントリーポイント
├── manage.py             # Django管理コマンド
└── requirements.txt
```

## Wiki機能の詳細

### ページのURL構造

```
/ または /wiki/                    # ホーム（階層図＋最近の更新）
/detail/<username>/<slug>/         # ページ詳細
/create/                           # 新規ページ作成
/create/<slug>/                    # slug指定で新規作成
/update/<username>/<slug>/         # ページ編集
/delete/<id>/                      # ページ削除
/settings/                         # 一括設定画面
/share/<share_code>/               # 共有ページ表示
/share/<share_code>/edit/          # 共有ページ編集
```

### 階層構造の実装

`lib/tree/tree.py`の`Tree`クラスがページのslugをスラッシュで分割し、階層構造を構築します。

**例**:
- `programming/python/basics` → programming > python > basics
- `programming/javascript/intro` → programming > javascript > intro

階層図は`gen_tree_htmls()`で自動生成され、各ページのナビゲーションに表示されます。

### CodeBuildによるマイグレーション

デプロイ時に`buildspec.yml`の`pre_build`フェーズで自動的にマイグレーションが実行されます：

```yaml
pre_build:
  commands:
    - echo "Running database migrations..."
    - cd Lambda
    - python manage.py migrate --noinput
    - cd ..
```

これにより、Lambda関数のデプロイ前にデータベースが最新の状態に更新されます。

## 参考リンク

- [Aurora DSQL Django Backend](https://github.com/awslabs/aurora-dsql-django)
- [Django on AWS Lambda](https://www.mangum.io/)
- [AWS Cognito JWT Authentication](https://github.com/h-akira/wambda)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) - HTMLパース（tree機能で使用）
