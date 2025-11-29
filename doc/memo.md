# Wiki Project App - メモ

## 認証とテンプレートコンテキストの問題（2025-11-29）

### 問題の概要

DSQL環境（本番環境）でログイン後もナビゲーションバーに「Log in」「Sign up」ボタンが表示され、「ユーザー名 - Logout」ボタンや「新規作成」「編集」ボタンが表示されない問題が発生した。

### 原因

DSQL環境では`django.contrib.auth`を`INSTALLED_APPS`から除外している（Aurora DSQLとの互換性のため）。そのため、`django.contrib.auth.context_processors.auth`コンテキストプロセッサーが利用できず、テンプレートに`user`変数が渡されていなかった。

#### 環境による設定の違い

**DSQL環境（本番）:**
```python
INSTALLED_APPS = [
  'accounts.apps.AccountsConfig',
  'wiki.apps.WikiConfig'
]
```

**ローカル環境:**
```python
INSTALLED_APPS = [
  'django.contrib.admin',
  'django.contrib.auth',  # ← これがDSQL環境にはない
  'django.contrib.contenttypes',
  ...
]
```

### 調査プロセス

1. **ログ確認**: Lambdaログで以下を確認
   ```
   Real Cognito token verified for user: h-akira
   Set request.user to h-akira, is_authenticated=True
   Final request.user: h-akira, is_authenticated=True
   GET / 200
   ```
   ミドルウェアで`request.user`は正しく設定されていた

2. **テンプレート確認**: base.htmlの`{% if user.is_authenticated %}`は正しく実装されていた

3. **settings.py確認**: DSQL環境のTEMPLATES設定で`django.contrib.auth.context_processors.auth`が利用できないことを発見

### 解決策

カスタムコンテキストプロセッサーを実装し、`request.user`をテンプレートコンテキストに渡すようにした。

#### 1. カスタムコンテキストプロセッサーの作成

**ファイル**: `Lambda/accounts/context_processors.py`

```python
"""
Custom context processors for accounts app
Provides user context without django.contrib.auth dependency
"""


def user(request):
  """
  Add user to template context

  This is a simplified version of django.contrib.auth.context_processors.auth
  that works without django.contrib.auth being in INSTALLED_APPS
  """
  return {
    'user': getattr(request, 'user', None)
  }
```

#### 2. settings.pyへの登録

**ファイル**: `Lambda/WikiProject/settings.py`

```python
if USE_DSQL:
  TEMPLATES = [
    {
      'BACKEND': 'django.template.backends.django.DjangoTemplates',
      'DIRS': [BASE_DIR / 'templates'],
      'APP_DIRS': True,
      'OPTIONS': {
        'context_processors': [
          'django.template.context_processors.debug',
          'django.template.context_processors.request',
          'accounts.context_processors.user',  # ← 追加
        ],
      },
    },
  ]
```

### 関連する実装

#### CognitoAuthMiddleware

**ファイル**: `Lambda/accounts/middleware.py`

ミドルウェアが`request.user`を設定する流れ：

1. リクエストからJWTトークンを取得（Cookie: `id_token`）
2. トークンをCognito JWKSで検証
3. トークンのclaimsからユーザー情報を取得
4. データベースでユーザーを取得/作成
5. `request.user`に設定

```python
if claims:
  request.cognito_claims = claims
  request.cognito_username = claims.get('cognito:username')

  user = self.get_or_create_user(claims)
  if user:
    request.user = user
```

#### Userモデル

**ファイル**: `Lambda/accounts/models.py`

カスタムUserモデルは`is_authenticated`プロパティを実装：

```python
@property
def is_authenticated(self):
  """Always return True for authenticated users"""
  return True
```

### その他の修正内容

この問題の調査・修正過程で、以下の改善も実施：

1. **ログアウト機能の実装**
   - `accounts/views.py`に`logout_page`関数を追加
   - `accounts/urls.py`に`/accounts/logout/`ルートを追加
   - `templates/base.html`のログアウトリンクを更新

2. **ログイン/サインアップページの認証チェック**
   - 認証済みユーザーが`/accounts/login/`や`/accounts/signup/`にアクセスした場合、ホームにリダイレクト

3. **静的ファイルパスの修正**
   - buildspec.ymlのS3 sync先を`s3://$S3_BUCKET/CloudFront/static/`に変更
   - CloudFrontのorigin_path（`/CloudFront`）とrequest_path（`/static/...`）を考慮

4. **ロギングの改善**
   - `settings.logger`から`logger = logging.getLogger('wiki')`に変更
   - ミドルウェアに詳細なデバッグログを追加

### 教訓

1. **環境による設定の違いに注意**: DSQL環境とローカル環境で`INSTALLED_APPS`が異なるため、依存関係に注意が必要

2. **コンテキストプロセッサーの重要性**: テンプレートで利用可能な変数は、ビュー関数から明示的に渡すか、コンテキストプロセッサーで提供する必要がある

3. **ログの活用**: ミドルウェアで`request.user`が正しく設定されているかログで確認することで、問題の切り分けができた

### 参考リンク

- Django Template Context Processors: https://docs.djangoproject.com/en/5.2/ref/templates/api/#built-in-template-context-processors
- AWS Aurora DSQL Django Backend: https://github.com/awslabs/aurora-dsql-django
- Cognito JWT認証実装: https://github.com/h-akira/wambda/blob/main/lib/wambda/authenticate.py
