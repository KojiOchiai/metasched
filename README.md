# metasched
dynamic scheduler

# setup
install uv from following [this instruction](https://docs.astral.sh/uv/getting-started/installation/)

# install
download
```bash
git clone https://github.com/KojiOchiai/metasched.git
```

move directory
```bash
cd metasched
```

setup env
```bash
uv sync
```

add path
```bash
export PYTHONPATH=$PYTHONPATH:.
```

# オフライン実行

## protocolファイルを作成する
- [protocol_8plates_fast.py](./sample/protocol_8plates_fast.py)を参考に実験手順ファイルを作成する
- 新しくプロトコルを作る際は`protocols`フォルダを作りそこで編集する
- start: Start が開始点になる。変数名は"start"固定

## 最適化だけして結果を見る
```bash
uv run scripts/optimize.py --protocolfile sample/protocol_parallel_fast.py --buffer 3
```

## 実行
```bash
uv run scripts/execute.py --protocolfile sample/protocol_parallel_fast.py --buffer 3
```
bufferにはprotocolの間に最低限開けて欲しい秒数を指定する

## スケジュールの確認
scripts/execute.pyを実行したのと同じディレクトリで以下を実行する。execute.pyの実行途中でも確認可能。
```bash
uv run scripts/print_schedule.py
```

## Resume
```bash
uv run scripts/execute.py --resume --buffer 3
```


# maholoでの実行
## 環境変数の設定
下の設定を~/.bashrcに追加
```bash
export MAHOLO_HOST=xx.x.x.xx # IP address of maholo FAPC
export MAHOLO_PORT=63001 # port that used by bioportal
export MAHOLO_BASE_PATH=C:\\BioApl\\DataSet\\Path\\for\\Protocols\\ # directory path for protocols
export MAHOLO_MICROSCOPE_IMAGE_DIR=/mnt/path/for/picture # directory path for picture
```
追加したら変数を読み込む
```bash
source ~/.bashrc
```

## protocol作成
オフライン実行と同じ形式でプロトコルを用意する。

## 本番用コマンド
```bash
uv run scripts/execute.py --protocolfile sample/protocol_parallel.py --buffer 60 --driver maholo
```

# Stop
実行したコマンドライン上でCtrl+Cでキャンセル。
