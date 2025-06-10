# テストスクリプト `test_main.py`

このディレクトリには、FastAPI アプリケーション `main.py` の挙動を確認する単体テストが置かれています。
`pytest` と `fastapi.testclient.TestClient` を使い、ユーザー登録・認証およびノート CRUD API の動作を検証します。

## 主なテスト内容
- **test_user_registration_and_login**: 新規ユーザー登録後にトークンを取得できるかを確認します。
- **test_crud_notes**: ノートの作成、取得、更新、削除が正しく行えるかをテストします。
- **test_auth_failure**: 認可されていないアクセスや他ユーザーのリソース操作が拒否されるかを確認します。

## 実行方法
1. プロジェクトのルートで README に記載された依存パッケージをインストールします。
   さらにテストには `httpx` が必要です。
   ```bash
   pip install httpx pytest
   ```
2. ルートディレクトリで次のコマンドを実行します。
   ```bash
   pytest
   ```
   テスト実行時には一時的な SQLite データベースが作成されるため、既存の `database.db` には影響しません。
