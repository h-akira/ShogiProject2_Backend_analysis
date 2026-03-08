# backend-analysis

将棋局面解析を非同期処理するマイクロサービス。YaneuraOu エンジンによる解析を SQS + Lambda Worker で実行する。

詳細設計は [docs/](docs/) を参照。

---

## 事前準備

### 1. Git サブモジュールの初期化

YaneuraOu エンジンのソースコードはサブモジュールとして管理されている。クローン後に以下を実行する。

```bash
git submodule update --init
```

### 2. AWS Systems Manager Parameter Store への登録

CI/CD パイプライン（CodeBuild）が DockerHub からベースイメージを pull する際に認証情報を参照する。
**デプロイ前に以下のパラメータを AWS マネジメントコンソールまたは CLI で登録しておくこと。**

| パラメータ名 | 種別 | 説明 |
|---|---|---|
| `/DockerHub/UserName` | String | DockerHub のユーザー名 |
| `/DockerHub/AccessToken` | SecureString | DockerHub のアクセストークン |

CLI での登録例:

```bash
aws ssm put-parameter \
  --name "/DockerHub/UserName" \
  --value "<your-username>" \
  --type String

aws ssm put-parameter \
  --name "/DockerHub/AccessToken" \
  --value "<your-access-token>" \
  --type SecureString
```

> CodeBuild の実行ロールに `ssm:GetParameters` の権限が付与されている必要がある。

### 3. インフラスタックの事前デプロイ

API Gateway の Cognito Authorizer 設定に、インフラスタックの CloudFormation エクスポートを使用する。
backend-analysis のデプロイ前にインフラスタック（`stack-sgp-${env}-infra-*`）がデプロイ済みであること。

---

## ローカル開発

### 依存ライブラリのインストール

```bash
cd Backend/analysis
python -m venv env
source env/bin/activate
pip install -r requirements-dev.txt
```

### テストの実行

```bash
pytest
```

### Docker ビルド（Worker Lambda）

```bash
cd Backend/analysis/worker
docker build -t sgp-analysis-worker .
```

---

## デプロイ

```bash
cd Backend/analysis
sam build
sam deploy \
  --stack-name stack-sgp-dev-backend-analysis \
  --parameter-overrides Env=dev \
  --capabilities CAPABILITY_NAMED_IAM \
  --resolve-s3 \
  --resolve-image-repos
```
