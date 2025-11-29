# モック機能仕様書

## 概要

ローカル開発環境でAWSサービス（SSM、Cognito）を使用せずにアプリケーションをテストするためのモック機能。

## 有効化

環境変数 `USE_MOCK=true` を設定することでモック機能が有効化されます。

```bash
export USE_MOCK=true
export USE_DSQL=false
export DEBUG=true
python manage.py runserver
```

## アーキテクチャ

### 初期化フロー

1. **manage.py起動時** ([Lambda/manage.py:15-28](../Lambda/manage.py))
   ```python
   if USE_MOCK:
     from moto import mock_aws
     mock = mock_aws()
     mock.start()

     # SSMモックデータ設定
     from mock.ssm import set_data as set_ssm_data
     set_ssm_data()

     # Cognitoモック初期化
     from mock.cognito import setup_mock_cognito
     setup_mock_cognito()
   ```

2. **settings.py読み込み** ([Lambda/WikiProject/settings.py:37](../Lambda/WikiProject/settings.py))
   ```python
   USE_MOCK = os.environ.get('USE_MOCK', 'false').lower() == 'true'
   ```

3. **各コンポーネントでの参照**
   - `accounts/views.py`: `settings.USE_MOCK`
   - `accounts/middleware.py`: `settings.USE_MOCK`

## モックSSM (Parameter Store)

### 実装

**ファイル**: `Lambda/mock/ssm.py`

### 提供パラメータ

| パラメータ名 | デフォルト値 | 説明 |
|------------|------------|------|
| `/Django/secret_key` | `django-insecure-vk7dnvxedeket+...` | Django秘密鍵 |
| `/Cognito/user_pool_id` | `us-east-1_ExamplePoolId` | Cognito User Pool ID |
| `/Cognito/client_id` | `testclientid` | Cognito App Client ID |
| `/Cognito/client_secret` | `testclientsecret` | Cognito App Client Secret |
| `/DSQL/cluster_endpoint` | `test-dsql-cluster.dsql...` | DSQL クラスターエンドポイント |

### 環境変数オーバーライド

環境変数で値をカスタマイズ可能：

```bash
export MOCK_COGNITO_USER_POOL_ID="my-pool-id"
export MOCK_COGNITO_CLIENT_ID="my-client-id"
```

## モックCognito

### 実装

**ファイル**: `Lambda/mock/cognito.py`

### データストレージ

```python
# インメモリストレージ（サーバー再起動で消失）
MOCK_USERS = {}  # ユーザーデータ
MOCK_CONFIRMATION_CODES = {}  # 未使用
```

### 提供機能

#### 1. ユーザー登録 (mock_sign_up)

```python
mock_sign_up(
  username: str,
  password: str,
  email: str,
  given_name: str = '',
  family_name: str = '',
  client_id: str = '',
  client_secret: str = ''
) -> dict
```

**動作**:
- ユーザー名重複チェック（既存なら `UsernameExistsException`）
- パスワード検証（8文字以上必須）
- **自動確認**: 常に `UserConfirmed: True` を返す
- インメモリストレージに保存

**返り値**:
```python
{
  'UserConfirmed': True,
  'UserSub': 'mock-{username}-sub'
}
```

**エラー**:
- `UsernameExistsException`: ユーザー名が既に存在
- `InvalidPasswordException`: パスワードが8文字未満

#### 2. ログイン認証 (mock_initiate_auth)

```python
mock_initiate_auth(
  username: str,
  password: str,
  client_id: str = '',
  client_secret: str = ''
) -> dict
```

**動作**:
- ユーザー存在チェック（存在しないと `UserNotFoundException`）
- パスワード照合（不一致で `NotAuthorizedException`）
- 確認済みチェック（未確認だと `UserNotConfirmedException`）
- モックJWTトークン生成

**トークン形式**:
```python
# ペイロード
{
  'sub': 'mock-{username}-sub',
  'cognito:username': username,
  'email': user['email'],
  'email_verified': 'true',
  'given_name': given_name,
  'family_name': family_name,
  'exp': timestamp + 3600
}

# トークン文字列
'mock-id-{base64_encode(json.dumps(payload))}'
'mock-access-{base64_encode(json.dumps(payload))}'
'mock-refresh-{base64_encode(json.dumps(payload))}'
```

**返り値**:
```python
{
  'AuthenticationResult': {
    'AccessToken': 'mock-access-...',
    'IdToken': 'mock-id-...',
    'RefreshToken': 'mock-refresh-...',
    'ExpiresIn': 3600,
    'TokenType': 'Bearer'
  }
}
```

**エラー**:
- `UserNotFoundException`: ユーザーが存在しない
- `NotAuthorizedException`: パスワード不一致
- `UserNotConfirmedException`: ユーザー未確認（通常発生しない）

#### 3. 確認コード検証 (mock_confirm_sign_up)

```python
mock_confirm_sign_up(
  username: str,
  confirmation_code: str,
  client_id: str = '',
  client_secret: str = ''
) -> dict
```

**動作**:
- **任意の確認コードを受け付ける**（実際の検証なし）
- ユーザーを確認済み状態に変更

**注**: `mock_sign_up`が自動確認するため、通常このAPIは使用されない

#### 4. テストユーザー自動作成

**setup_mock_cognito()** 実行時に自動作成：

```python
username: 'testuser'
email: 'test@example.com'
password: 'TestPass123!'
given_name: 'Test'
family_name: 'User'
confirmed: True
```

### 使用箇所

#### accounts/views.py

各認証関数で`settings.USE_MOCK`に基づいて分岐：

```python
if settings.USE_MOCK:
  # モック認証
  response = mock_initiate_auth(username, password, ...)
else:
  # 実際のCognito認証
  client = boto3.client('cognito-idp')
  response = client.admin_initiate_auth(...)
```

- `login_page()`: ログイン処理
- `signup_page()`: サインアップ処理
- `confirm_page()`: 確認コード処理

#### accounts/middleware.py

**CognitoAuthMiddleware.verify_token()**:

```python
if settings.USE_MOCK:
  # モックトークンのデコード
  if token.startswith('mock-id-'):
    payload_b64 = token.replace('mock-id-', '')
    claims = json.loads(base64.b64decode(payload_b64))
    return claims
else:
  # 実際のJWT検証（Cognito公開鍵使用）
  signing_key = self.jwk_client.get_signing_key_from_jwt(token)
  decoded = jwt.decode(token, signing_key.key, algorithms=['RS256'], ...)
  return decoded
```

## できること・制限事項

### ✅ できること

1. **完全なローカル認証フロー**
   - サインアップ → ログイン → 認証状態維持

2. **AWSアカウント不要**
   - 実際のCognitoサービスへの接続不要
   - AWS認証情報不要

3. **複数ユーザー作成**
   - サインアップで任意の数のユーザーを作成可能
   - サーバー再起動までは永続化

4. **エラーハンドリングテスト**
   - 重複ユーザー名
   - パスワード不一致
   - 存在しないユーザー

5. **自動テストユーザー**
   - 毎回`testuser`が自動作成される
   - すぐにログインテスト可能

### ❌ 制限事項・できないこと

1. **JWT署名検証**
   - モックトークンは疑似的なbase64エンコード
   - 実際のCognito公開鍵での検証は行われない
   - ただし、ミドルウェアは正しくデコード可能

2. **データ永続化**
   - サーバー再起動で全ユーザーデータが消失
   - `testuser`は毎回再作成される

3. **メール送信**
   - 確認コードメールは送信されない
   - 自動確認されるため不要

4. **リフレッシュトークン機能**
   - トークンは生成されるが、リフレッシュ処理は未実装
   - ミドルウェアの`refresh_tokens()`はモック非対応

5. **本番Cognitoとの互換性**
   - モックと本番は完全に分離
   - トークン形式が異なる

6. **MFA (多要素認証)**
   - MFAフローは未実装

7. **パスワードリセット**
   - パスワード変更・リセット機能は未実装

## テスト手順

### 基本的なログインフロー

1. サーバー起動
   ```bash
   cd /Users/hakira/Programs/WikiProject/WikiProject_App/Lambda
   export USE_MOCK=true
   export USE_DSQL=false
   export DEBUG=true
   python manage.py runserver 0.0.0.0:8000
   ```

2. ブラウザで `http://localhost:8000/accounts/login/` にアクセス

3. テストユーザーでログイン
   - Username: `testuser`
   - Password: `TestPass123!`

4. ホームページにリダイレクト
   - ナビゲーションバーにユーザー名表示
   - ログイン状態が維持される

### 新規ユーザー作成

1. `http://localhost:8000/accounts/signup/` にアクセス

2. 任意の情報を入力
   - Username: 任意（重複不可）
   - Email: 任意
   - Password: 8文字以上

3. サインアップ成功
   - 自動確認される（メール不要）
   - すぐにログイン可能

### エラーテスト

1. **重複ユーザー名**
   - 既存ユーザーと同じユーザー名でサインアップ
   - エラー: "Username already exists"

2. **パスワード不一致**
   - 間違ったパスワードでログイン
   - エラー: "Incorrect username or password"

3. **存在しないユーザー**
   - 未登録ユーザーでログイン
   - エラー: "User not found"

## 本番環境への切り替え

```bash
export USE_MOCK=false
export USE_DSQL=true
export DEBUG=false
# AWS認証情報とCognito設定が必要
python manage.py runserver
```

本番環境では：
- 実際のAWS SSM Parameter Storeから設定取得
- 実際のCognito User Poolで認証
- JWT署名検証が有効化
- データベースはAurora DSQL

## トラブルシューティング

### ログイン後もログイン状態にならない

**原因**: ミドルウェアがモックトークンを認識していない

**確認**:
```bash
# サーバーログを確認
# "Mock token verified for user: testuser" が表示されるべき
```

**解決**:
- ブラウザのCookieをクリア
- サーバーを再起動
- `settings.USE_MOCK`が正しく設定されているか確認

### "User not found" エラー

**原因**: サーバー再起動でユーザーデータが消失

**解決**:
- `testuser`でログイン（自動作成される）
- または新規サインアップ

### "Invalid mock token format" エラー

**原因**: 古いトークンがCookieに残っている

**解決**:
- ブラウザのCookieをクリア
- 再度ログイン

## 今後の改善案

1. **SQLiteへの永続化**
   - モックユーザーをSQLiteに保存
   - サーバー再起動後もデータ維持

2. **リフレッシュトークン対応**
   - ミドルウェアでのモックトークンリフレッシュ実装

3. **MFAサポート**
   - 2段階認証フローのモック

4. **パスワードリセット**
   - パスワード変更・リセットフローのモック

5. **トークン有効期限チェック**
   - `exp`クレームの検証

6. **カスタムクレーム**
   - グループ、ロールなどのカスタム属性サポート
