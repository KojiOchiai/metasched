# metashed
dynamic scheduler

# install
download
```bash
git clone git@github.com:KojiOchiai/metashed.git
```
install
```bash
uv sync
```

# 使い方

## protocolファイルを作成する
- [protocol_8plates_fast.py](./sample/protocol_8plates_fast.py)を参考に実験手順ファイルを作成する
- start: Start が開始点になる。変数名は"start"固定

## 実行コマンド
offlline実行
```bash
uv run main.py sample/protocol_8plates_fast.py --load executor_state
```

# simulator server の起動
```bash
uv run python drivers/maholo/sim_server.py 
```

# maholoでの実行
下の設定を~/.bashrcに追加
```bash
export MAHOLO_HOST=10.5.1.11 # IP address of maholo FAPC
export MAHOLO_PORT=63001 # port that used by bioportal
export MAHOLO_BASE_PATH=C:\\BioApl\\DataSet\\cellculture-08\\Protocol\\YGI\\Round2\\ # directory path for protocols
export MAHOLO_MICROSCOPE_IMAGE_DIR=/mnt/nikon/DS/Documents/Round2/ # directory path for picture
```

本番用コマンド
```bash
uv run main.py sample/protocol_8plates_fast.py --load executor_state --driver maholo
```

# Stop
実行したコマンドライン上でCtrl+Cでキャンセル。

# Resume
- コマンドを再度打つと、
  - maholoを走らせている途中で停止 → そのタスクの最初から実行再開
  - それ以外の場合 → 残りのスケジュールを実行

## 残りのスケジュール確認
```basy
cat executor_state/awaitlist.json 
```