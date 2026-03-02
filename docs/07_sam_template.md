# SAM テンプレート設計

## 概要

解析 API の AWS リソースを SAM テンプレートで定義する。命名規約は [units_contracts.md](../../../docs/units_contracts.md) に準拠する。

| 項目 | 値 |
|------|-----|
| テンプレートファイル | `Backend/analysis/template.yaml` |
| スタック名 | `stack-sgp-${env}-backend-analysis` |
| Transform | `AWS::Serverless-2016-10-31` |

---

## Parameters

| パラメータ名 | 型 | デフォルト | 説明 |
|-------------|-----|---------|------|
| `Env` | String | なし | 環境識別子 (`dev`, `pro`) |
| `MaxConcurrency` | String | `8` | Worker Lambda の最大同時実行数 |

### Cognito 情報の取得

インフラスタックからの CloudFormation エクスポートとして取得する。

| エクスポート名 | 値 | 用途 |
|--------------|-----|------|
| `sgp-${Env}-infra-CognitoUserPoolArn` | User Pool ARN | API Gateway の Cognito Authorizer |

---

## Globals

```yaml
Globals:
  Function:
    Runtime: python3.13
  Api:
    Cors:
      AllowMethods: "'GET,POST,OPTIONS'"
      AllowHeaders: "'Content-Type,Authorization'"
      AllowOrigin: "'*'"
      AllowCredentials: false
```

---

## Resources

### DynamoDB テーブル (`AnalysisTable`)

[03_dynamodb_design.md](03_dynamodb_design.md) に基づくデータストア定義。

```yaml
AnalysisTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub "dynamodb-sgp-${Env}-backend-analysis"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: pk
        AttributeType: S
      - AttributeName: sk
        AttributeType: S
    KeySchema:
      - AttributeName: pk
        KeyType: HASH
      - AttributeName: sk
        KeyType: RANGE
    TimeToLiveSpecification:
      AttributeName: ttl
      Enabled: true
```

### SQS FIFO キュー (`AnalysisQueue`)

```yaml
AnalysisDeadLetterQueue:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub "sqs-sgp-${Env}-backend-analysis-dlq.fifo"
    FifoQueue: true

AnalysisQueue:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub "sqs-sgp-${Env}-backend-analysis.fifo"
    FifoQueue: true
    VisibilityTimeout: 120
    MessageRetentionPeriod: 300
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt AnalysisDeadLetterQueue.Arn
      maxReceiveCount: 2
```

| 設定 | 値 | 説明 |
|------|-----|------|
| FifoQueue | true | ユーザー単位での順序保証 |
| VisibilityTimeout | 120 秒 | Worker Lambda のタイムアウト（30 秒）の 4 倍 |
| MessageRetentionPeriod | 300 秒 | リトライ + DLQ 移動に十分な保持期間 |
| maxReceiveCount | 2 | 2 回失敗で DLQ に移動 |

### API Gateway (`ApiGateway`)

```yaml
ApiGateway:
  Type: AWS::Serverless::Api
  Properties:
    StageName: Prod
    Auth:
      DefaultAuthorizer: CognitoAuthorizer
      Authorizers:
        CognitoAuthorizer:
          UserPoolArn: !ImportValue
            Fn::Sub: "sgp-${Env}-infra-CognitoUserPoolArn"
          Identity:
            Header: Authorization
```

### API Lambda 関数 (`ApiFunction`)

| 項目 | 値 |
|------|-----|
| FunctionName | `lambda-sgp-${Env}-backend-analysis-api` |
| CodeUri | `api/` |
| Handler | `app.lambda_handler` |
| Timeout | 10 |
| MemorySize | 256 |

#### 環境変数

| 変数名 | 値 |
|--------|-----|
| `DYNAMODB_TABLE_NAME` | `!Ref AnalysisTable` |
| `SQS_QUEUE_URL` | `!GetAtt AnalysisQueue.QueueUrl` |

#### IAM ポリシー

| アクション | 対象 | 用途 |
|-----------|------|------|
| `dynamodb:PutItem` | AnalysisTable | 解析リクエストの作成 |
| `dynamodb:GetItem` | AnalysisTable | 解析結果の取得 |
| `sqs:SendMessage` | AnalysisQueue | 解析メッセージの送信 |

#### API イベント定義

| イベント名 | Path | Method | Auth |
|-----------|------|--------|------|
| `CreateAnalysis` | `/api/v1/analysis/requests` | POST | デフォルト (Cognito) |
| `GetAnalysis` | `/api/v1/analysis/requests/{aid}` | GET | デフォルト (Cognito) |

### Worker Lambda 関数 (`WorkerFunction`)

| 項目 | 値 |
|------|-----|
| FunctionName | `lambda-sgp-${Env}-backend-analysis-worker` |
| PackageType | Image |
| Timeout | 30 |
| MemorySize | 2048 |

```yaml
WorkerFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub "lambda-sgp-${Env}-backend-analysis-worker"
    PackageType: Image
    Timeout: 30
    MemorySize: 2048
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: !Ref AnalysisTable
    Policies:
      - Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action:
              - dynamodb:UpdateItem
            Resource: !GetAtt AnalysisTable.Arn
    Events:
      SQSEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt AnalysisQueue.Arn
          BatchSize: 1
          ScalingConfig:
            MaximumConcurrency: !Ref MaxConcurrency
  Metadata:
    DockerTag: latest
    DockerContext: ./worker
    Dockerfile: Dockerfile
```

| 設定 | 値 | 説明 |
|------|-----|------|
| PackageType | Image | Docker コンテナイメージとしてデプロイ |
| MemorySize | 2048 MB | YaneuraOu エンジン実行に必要 |
| Timeout | 30 秒 | 最大思考時間（10 秒）+ オーバーヘッド |
| BatchSize | 1 | 1 メッセージずつ処理 |
| MaximumConcurrency | パラメータ（デフォルト 8） | Worker の最大同時実行数 |

### DLQ Lambda 関数 (`DlqFunction`)

Worker Lambda がインフラ障害（OOMKill、コンテナクラッシュ、Lambda タイムアウト等）で処理できなかったメッセージを受け取り、DynamoDB のステータスを `failed` に更新する。

| 項目 | 値 |
|------|-----|
| FunctionName | `lambda-sgp-${Env}-backend-analysis-dlq` |
| CodeUri | `dlq/` |
| Handler | `handler.handler` |
| Timeout | 10 |
| MemorySize | 128 |

```yaml
DlqFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub "lambda-sgp-${Env}-backend-analysis-dlq"
    CodeUri: dlq/
    Handler: handler.handler
    Timeout: 10
    MemorySize: 128
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: !Ref AnalysisTable
    Policies:
      - Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action:
              - dynamodb:UpdateItem
            Resource: !GetAtt AnalysisTable.Arn
    Events:
      DLQEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt AnalysisDeadLetterQueue.Arn
          BatchSize: 1
```

---

## Outputs

インフラスタック（CloudFront のオリジン設定）に公開する出力。[units_contracts.md](../../../docs/units_contracts.md) のエクスポート仕様に準拠する。

```yaml
Outputs:
  ApiGatewayId:
    Description: API Gateway REST API ID
    Value: !Ref ApiGateway
    Export:
      Name: !Sub "sgp-${Env}-backend-analysis-ApiGatewayId"
  ApiGatewayStageName:
    Description: API Gateway stage name
    Value: Prod
    Export:
      Name: !Sub "sgp-${Env}-backend-analysis-ApiGatewayStageName"
```

---

## デプロイ

```bash
sam build
sam deploy \
  --stack-name stack-sgp-dev-backend-analysis \
  --parameter-overrides Env=dev \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --resolve-image-repos
```

> `--resolve-image-repos` は Docker イメージ用の ECR リポジトリを自動作成する。Cognito 情報は `Fn::ImportValue` で自動取得するため、パラメータとして渡す必要はない。インフラスタック（`stack-sgp-${env}-infra-*`）が先にデプロイされている必要がある。
