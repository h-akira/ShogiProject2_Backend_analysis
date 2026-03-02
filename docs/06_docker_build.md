# Docker ビルド設計

## 概要

Worker Lambda は Docker コンテナイメージとしてデプロイされる。コンテナ内に YaneuraOu エンジンをコンパイルし、NNUE 評価関数ファイルと共に配置する。

旧システム（`ShogiProject_old/ShogiProject_Analysis/ShogiCPU/Dockerfile`）の構成を踏襲しつつ、新システム向けに調整する。

---

## Dockerfile

```dockerfile
FROM public.ecr.aws/lambda/python:3.13

# Install build tools for YaneuraOu compilation
RUN dnf install -y gcc gcc-c++ make

WORKDIR /var/task

# Copy engine source and pre-configured files
COPY Engine Engine
COPY YaneuraOu YaneuraOu

# Compile YaneuraOu
WORKDIR /var/task/YaneuraOu/source
RUN make && mv YaneuraOu-by-gcc /var/task/Engine/

# Copy Lambda handler
WORKDIR /var/task
COPY handler.py ${LAMBDA_TASK_ROOT}
COPY engine.py ${LAMBDA_TASK_ROOT}

CMD [ "handler.handler" ]
```

### ベースイメージ

| 項目 | 値 |
|------|-----|
| ベースイメージ | `public.ecr.aws/lambda/python:3.13` |
| アーキテクチャ | x86_64 |
| OS | Amazon Linux 2023 |

### ビルドステージ

1. **ビルドツールのインストール**: `gcc`, `g++`, `make` を dnf でインストール
2. **ソースコードのコピー**: Engine ディレクトリ（評価関数）と YaneuraOu ソースをコピー
3. **コンパイル**: `make` で YaneuraOu をビルドし、バイナリを Engine ディレクトリに移動
4. **ハンドラのコピー**: `handler.py` と `engine.py` を `LAMBDA_TASK_ROOT` にコピー

---

## YaneuraOu のビルド設定

### Makefile の調整

CI/CD パイプライン（CodeBuild の `buildspec.yml`）で以下の調整を行う:

| 設定 | デフォルト | 変更後 | 理由 |
|------|---------|--------|------|
| コンパイラ | `clang++` | `g++` | Lambda コンテナ環境に clang がないため |
| ターゲット CPU | `AVX2` | `SSE42` | Lambda の CPU が AVX2 をサポートしない可能性があるため |

```bash
# buildspec.yml での Makefile 編集
sed -i 's/^COMPILER = clang++/#COMPILER = clang++/' YaneuraOu/source/Makefile
sed -i 's/^#COMPILER = g++/COMPILER = g++/' YaneuraOu/source/Makefile
sed -i 's/^TARGET_CPU = AVX2/#TARGET_CPU = AVX2/' YaneuraOu/source/Makefile
sed -i 's/^#TARGET_CPU = SSE42/TARGET_CPU = SSE42/' YaneuraOu/source/Makefile
```

### NNUE 評価関数

| 項目 | 値 |
|------|-----|
| 評価関数 | Suisho5 (水匠5) |
| ファイル名 | `nn.bin` |
| 配置場所 | `Engine/eval/nn.bin` |
| ダウンロード元 | YaneuraOu GitHub Releases |

CI/CD パイプラインで評価関数をダウンロードする:

```bash
# buildspec.yml での評価関数ダウンロード
curl -LS -o nn.7z https://github.com/yaneurao/YaneuraOu/releases/download/suisho5/Suisho5.7z
7z x nn.7z
mkdir -p worker/Engine/eval
mv nn.bin worker/Engine/eval/
```

---

## YaneuraOu の Git サブモジュール

YaneuraOu のソースコードは Git サブモジュールとして管理する。

### .gitmodules

```
[submodule "worker/YaneuraOu"]
	path = worker/YaneuraOu
	url = https://github.com/yaneurao/YaneuraOu.git
```

---

## コンテナ内のファイル配置

ビルド後のコンテナ内の最終的なファイル構成:

```
/var/task/
├── handler.py                      # Lambda ハンドラ
├── engine.py                       # エンジン通信モジュール
└── Engine/
    ├── YaneuraOu-by-gcc            # コンパイル済みバイナリ (~30 MB)
    └── eval/
        └── nn.bin                   # NNUE 評価関数 (~50 MB)
```

---

## イメージサイズの見積もり

| コンポーネント | サイズ（概算） |
|-------------|------------|
| Lambda ベースイメージ | ~300 MB |
| ビルドツール (gcc 等) | ~200 MB |
| YaneuraOu バイナリ | ~30 MB |
| NNUE 評価関数 | ~50 MB |
| Python ハンドラ | ~10 KB |
| **合計** | **~580 MB** |

> Lambda コンテナイメージの上限は 10 GB。十分に収まる。

---

## ローカルビルド・テスト

### ビルド

```bash
cd Backend/analysis/worker
docker build -t sgp-analysis-worker .
```

### 動作確認

```bash
docker run --rm -p 9000:8080 sgp-analysis-worker

# 別ターミナルで
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"Records": [{"body": "{\"username\": \"test\", \"aid\": \"test123\", \"sfen\": \"lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1\", \"thinking_time\": 3000}"}]}'
```

> ローカルテストでは DynamoDB のモック（LocalStack 等）が必要。
