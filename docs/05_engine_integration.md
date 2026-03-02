# YaneuraOu エンジン連携設計

## 概要

Worker Lambda は YaneuraOu 将棋エンジンを子プロセスとして起動し、USI (Universal Shogi Interface) プロトコルで通信する。エンジンは Docker コンテナイメージ内にコンパイル済みバイナリとして同梱される。

---

## YaneuraOu について

| 項目 | 値 |
|------|-----|
| エンジン | YaneuraOu（やねうら王） |
| プロトコル | USI (Universal Shogi Interface) |
| 評価関数 | NNUE（Suisho5） |
| ビルド対象 | Linux x86_64（SSE4.2） |
| コンパイラ | g++ (GCC) |

---

## エンジン通信フロー

### 初期化シーケンス

```
Lambda → Engine: usi
Engine → Lambda: id name YaneuraOu ...
Engine → Lambda: usiok
Lambda → Engine: setoption name MultiPV value 3
Lambda → Engine: isready
Engine → Lambda: readyok
```

### 解析実行シーケンス

```
Lambda → Engine: position sfen <SFEN>
Lambda → Engine: go movetime <thinking_time>
Engine → Lambda: info depth ... multipv 1 score cp 450 ... pv 7g7f 8c8d ...
Engine → Lambda: info depth ... multipv 2 score cp 420 ... pv 2g2f 8c8d ...
Engine → Lambda: info depth ... multipv 3 score cp 380 ... pv 5i6h 8c8d ...
Engine → Lambda: bestmove 7g7f
```

### 終了シーケンス

```
Lambda → Engine: quit
```

---

## engine.py の設計

### クラス設計

```python
class ShogiEngine:
    """YaneuraOu engine wrapper using USI protocol."""

    def __init__(self, engine_path: str, multipv: int = 3):
        self._engine_path = engine_path
        self._multipv = multipv
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        """Start the engine process and initialize via USI protocol."""

    def analyze(self, sfen: str, movetime: int) -> list[dict]:
        """Analyze a position and return candidates."""

    def quit(self) -> None:
        """Terminate the engine process."""
```

### start() の処理

1. `subprocess.Popen` でエンジンプロセスを起動する
   - `stdin=subprocess.PIPE`
   - `stdout=subprocess.PIPE`
   - `stderr=subprocess.PIPE`
2. `usi` コマンドを送信し、`usiok` を受信するまで待機する
3. `setoption name MultiPV value {multipv}` を送信する
4. `isready` を送信し、`readyok` を受信するまで待機する

### analyze() の処理

1. `position sfen {sfen}` を送信する
2. `go movetime {movetime}` を送信する
3. `bestmove` を受信するまで出力を読み取る
4. `info` 行から候補手情報をパースする
5. 候補手リストを返却する

### quit() の処理

1. `quit` コマンドを送信する
2. プロセスの終了を待機する（タイムアウト付き）
3. タイムアウト時は `kill()` で強制終了する

---

## USI 出力のパース

### info 行の形式

```
info depth 20 seldepth 30 multipv 1 score cp 450 nodes 1234567 nps 500000 pv 7g7f 8c8d 2g2f ...
info depth 20 seldepth 28 multipv 2 score cp 420 nodes 1234567 nps 500000 pv 2g2f 8c8d 7g7f ...
info depth 20 seldepth 25 multipv 3 score cp 380 nodes 1234567 nps 500000 pv 5i6h 8c8d 7g7f ...
```

### パース対象

| フィールド | 説明 | パース方法 |
|-----------|------|----------|
| `multipv` | 候補手の順位 | `multipv (\d+)` |
| `score cp` | 評価値（centipawn） | `score cp (-?\d+)` |
| `score mate` | 詰み手数（正: 自分の勝ち、負: 相手の勝ち） | `score mate (-?\d+)` |
| `pv` | 読み筋（USI 形式の手の列） | `pv (.+)$` |

### パース用正規表現

```python
INFO_PATTERN = re.compile(
    r"score (cp|mate) (-?\d+).*multipv (\d+).*pv (.+)"
)
```

### パース結果

最終的に `bestmove` が出力される直前の各 `multipv` の最も深い `info` 行を採用する。

```python
# Result format
[
    {"rank": 1, "score": 450, "pv": "7g7f 8c8d 2g2f"},
    {"rank": 2, "score": 420, "pv": "2g2f 8c8d 7g7f"},
    {"rank": 3, "score": 380, "pv": "5i6h 8c8d 7g7f"},
]
```

### 詰み（mate）の評価値変換

`score mate N` の場合、`score cp` に変換する:

| 条件 | 変換値 | 説明 |
|------|--------|------|
| `score mate N` (N > 0) | `+30000` | 自分が N 手で詰ます |
| `score mate N` (N < 0) | `-30000` | 相手が |N| 手で詰ます |

---

## エラーハンドリング

### エンジン起動失敗

エンジンバイナリが見つからない、または実行権限がない場合:
- `FileNotFoundError` または `PermissionError` を捕捉
- DynamoDB に `status=failed`, `error_message="Engine startup failed"` を記録

### エンジンタイムアウト

`bestmove` が返ってこない場合:
- `thinking_time + 5000ms` のタイムアウトを設定
- タイムアウト時はプロセスを `kill()` して強制終了
- DynamoDB に `status=failed`, `error_message="Engine process timed out"` を記録

### 不正な SFEN

エンジンが不正な SFEN を受け取った場合、エンジンの挙動は未定義である。この場合 `bestmove` が返らずタイムアウトとなるため、上記のタイムアウト処理で対応する。

---

## エンジン関連ファイルの配置

Docker コンテナ内のファイル配置:

```
/var/task/
├── handler.py
├── engine.py
└── Engine/
    ├── YaneuraOu-by-gcc    # コンパイル済みバイナリ
    └── eval/
        └── nn.bin           # NNUE 評価関数ファイル (Suisho5)
```

### エンジンパス

```python
ENGINE_PATH = "/var/task/Engine/YaneuraOu-by-gcc"
```

エンジンは `Engine/` ディレクトリからの相対パスで評価関数ファイルを自動検出する。

---

## パフォーマンス考慮事項

| 項目 | 値 | 備考 |
|------|-----|------|
| MultiPV | 3 | 候補手数。増やすと探索効率が低下する |
| 思考時間 | 3000 / 5000 / 10000 ms | ユーザーが選択 |
| Lambda メモリ | 2048 MB | エンジン実行に必要な最小メモリ |
| Lambda タイムアウト | 30 秒 | 最大思考時間（10 秒）+ オーバーヘッド |
| コールドスタート | 数秒〜10 秒程度 | Docker コンテナ起動のため zip より遅い |
