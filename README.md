# metasched
constraint-based scheduling optimizer and executor for laboratory automation workflows

# Setup
install uv from following [this instruction](https://docs.astral.sh/uv/getting-started/installation/)

# Install
download
```bash
git clone git@github.com:KojiOchiai/metasched.git
```
install
```bash
uv sync
```

# オフライン実行

## protocolファイルを作成する
- [protocol_8plates_fast.py](./sample_protocols/protocol_8plates_fast.py)を参考に実験手順ファイルを作成する
- start: Start が開始点になる。変数名は"start"固定

## 最適化だけして結果を見る
```bash
uv run metasched optimize --protocolfile sample_protocols/protocol_parallel_fast.py --buffer 3
```

## 実行
```bash
uv run metasched execute --protocolfile sample_protocols/protocol_parallel_fast.py --buffer 3
```
bufferにはprotocolの間に最低限開けて欲しい秒数を指定する

## スケジュールの確認
executeを実行したのと同じディレクトリで以下を実行する。実行途中でも確認可能。
```bash
uv run metasched print-schedule
```

## Resume
```bash
uv run metasched execute --resume
```


# maholoでの実行
## 環境変数の設定
プロジェクトルートに`.env`ファイルを作成し、以下の変数を設定する。

**必須:**
```
MAHOLO_HOST=xx.x.x.xx                                          # IP address of maholo FAPC
MAHOLO_PORT=63001                                               # port that used by bioportal
MAHOLO_BASE_PATH=C:\BioApl\DataSet\Path\for\Protocols\          # directory path for protocols
```

**オプション:**
```
MAHOLO_MICROSCOPE_IMAGE_DIR=/mnt/path/for/picture               # 顕微鏡画像の保存先ディレクトリ
```
`MAHOLO_MICROSCOPE_IMAGE_DIR`は省略可。設定すると顕微鏡画像のパスがログに記録される。未設定でも動作に影響はない。

### MAHOLO_MICROSCOPE_IMAGE_DIRの設定例
実際にアクセスするフォルダ構成：/mnt//nikon_save/2025_12_05/tiling/220513_test.tif
MAHOLO_MICROSCOPE_IMAGE_DIR=/mnt/nikon_save/

> **Note:** 環境変数(`~/.bashrc`の`export`など)でも設定可能。`.env`ファイルと環境変数の両方がある場合、環境変数が優先される。

## protocol作成
オフライン実行と同じ形式でプロトコルを用意する。

## 本番用コマンド
```bash
uv run metasched execute --protocolfile sample_protocols/protocol_parallel.py --buffer 60 --driver maholo
```

# ログの可視化
実行ログをインタラクティブなHTMLタイムラインとして可視化する。

## 最新のログを可視化
```bash
uv run python scripts/analyze_log.py
```

## 一覧から選択
```bash
uv run python scripts/analyze_log.py --list
```

## ログファイルを直接指定
```bash
uv run python scripts/analyze_log.py logs/metasched_20260404_005415.log
```

- 予定時刻(薄青)と実際の実行時刻(緑/黄/赤)を重ねて表示
- ホバーでscheduled/started/finished/duration/delayの詳細を確認
- 再最適化ポイントをマーカーで表示(legendクリックで切替)

# Stop
実行したコマンドライン上でCtrl+Cでキャンセル。
