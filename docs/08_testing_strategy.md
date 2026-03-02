# テスト方針

## 概要

pytest + moto を用いて、API Lambda の各レイヤーおよび Worker Lambda のエンジン通信をテストする。DynamoDB と SQS は moto でモックし、YaneuraOu エンジンは subprocess のモックでテストする。

---

## 依存パッケージ

### `requirements-dev.txt`

```
-r requirements.txt
pytest
moto[dynamodb,sqs]
```

---

## pytest 設定

### `pytest.ini`

```ini
[pytest]
pythonpath = api
testpaths = tests
```

---

## 共通フィクスチャ (`tests/conftest.py`)

### 環境変数の設定

テスト開始前に、モジュールのインポートより先に環境変数を設定する。

```python
import os

os.environ["DYNAMODB_TABLE_NAME"] = "test-analysis-table"
os.environ["SQS_QUEUE_URL"] = "https://sqs.ap-northeast-1.amazonaws.com/123456789012/test-queue.fifo"
os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
```

### `aws_mock` フィクスチャ

moto で DynamoDB と SQS をモックする。

```python
@pytest.fixture
def aws_mock():
    with mock_aws():
        yield
```

### `dynamodb_table` フィクスチャ

テスト用 DynamoDB テーブルを作成する。

```python
@pytest.fixture
def dynamodb_table(aws_mock):
    dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
    table = dynamodb.create_table(
        TableName="test-analysis-table",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    yield table
```

### `sqs_queue` フィクスチャ

テスト用 SQS FIFO キューを作成する。

```python
@pytest.fixture
def sqs_queue(aws_mock):
    sqs = boto3.resource("sqs", region_name="ap-northeast-1")
    queue = sqs.create_queue(
        QueueName="test-queue.fifo",
        Attributes={"FifoQueue": "true"},
    )
    yield queue
```

### `make_apigw_event` ヘルパー

API Gateway プロキシイベントを生成する。

```python
def make_apigw_event(
    method: str,
    path: str,
    body: dict | None = None,
    username: str | None = None,
    path_params: dict | None = None,
) -> dict:
    event = {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else None,
        "queryStringParameters": None,
        "pathParameters": path_params,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {},
    }
    if username:
        event["requestContext"] = {
            "authorizer": {
                "claims": {
                    "cognito:username": username,
                },
            },
        }
    return event
```

---

## テスト対象一覧

### リポジトリ層テスト (`test_repositories.py`)

DynamoDB への CRUD 操作を直接テストする。

| テストケース | 検証内容 |
|------------|---------|
| `test_put_and_get_analysis` | PutItem → GetItem で正しく取得できること |
| `test_get_analysis_not_found` | 存在しない aid で None が返ること |
| `test_get_analysis_wrong_user` | 他ユーザーの aid でアクセスできないこと |
| `test_update_status_running` | status が running に更新されること |
| `test_update_status_completed` | status と candidates が正しく更新されること |
| `test_update_status_failed` | status と error_message が正しく更新されること |

### サービス層テスト (`test_services.py`)

ビジネスロジックとバリデーションをテストする。

| テストケース | 検証内容 |
|------------|---------|
| `test_create_analysis_success` | 正常な作成で {aid, status} が返ること |
| `test_create_analysis_sqs_message` | SQS に正しいメッセージが送信されること |
| `test_create_analysis_missing_sfen` | sfen 未指定で ValidationError |
| `test_create_analysis_empty_sfen` | 空の sfen で ValidationError |
| `test_create_analysis_invalid_thinking_time` | 不正な thinking_time で ValidationError |
| `test_get_analysis_success` | 正常取得で AnalysisResult が返ること |
| `test_get_analysis_not_found` | 存在しない aid で NotFoundError |

### ルート層統合テスト (`test_routes.py`)

`make_apigw_event` + `app.lambda_handler` でエンドツーエンドのテストを行う。

| テストケース | 検証内容 |
|------------|---------|
| `test_create_analysis_202` | ステータス 202、{aid, status} レスポンス |
| `test_create_analysis_400_missing_sfen` | ステータス 400、バリデーションエラー |
| `test_create_analysis_400_invalid_thinking_time` | ステータス 400、バリデーションエラー |
| `test_get_analysis_200_pending` | ステータス 200、status=pending のレスポンス |
| `test_get_analysis_200_completed` | ステータス 200、candidates 含むレスポンス |
| `test_get_analysis_200_failed` | ステータス 200、error_message 含むレスポンス |
| `test_get_analysis_404` | ステータス 404、Error スキーマ準拠 |

### エンジン通信テスト (`test_engine.py`)

YaneuraOu エンジンとの USI 通信をテストする。subprocess をモックして実施する。

| テストケース | 検証内容 |
|------------|---------|
| `test_parse_info_cp` | `score cp` の info 行が正しくパースされること |
| `test_parse_info_mate` | `score mate` の info 行が正しくパースされること |
| `test_parse_multipv` | MultiPV の結果が rank 順にソートされること |
| `test_engine_start_and_quit` | エンジンの起動・終了シーケンスが正しいこと |
| `test_analyze_success` | 正常な解析で候補手リストが返ること |
| `test_analyze_timeout` | エンジンタイムアウト時に例外が発生すること |
| `test_engine_startup_failure` | エンジン起動失敗時に例外が発生すること |

---

## テスト命名規約

```
test_<対象>_<シナリオ>
```

例:
- `test_create_analysis_success`
- `test_create_analysis_missing_sfen`
- `test_get_analysis_not_found`
- `test_parse_info_cp`
- `test_analyze_timeout`

---

## テスト実行

```bash
cd Backend/analysis
python -m pytest tests/ -v
```
