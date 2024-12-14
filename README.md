# summaly-py
misskey-dev/summalyのPython実装。

<!--クライアント部分はpysummaryとしてPyPIからインストールできます。-->
## 特徴
### 独自対応
#### Skeb
* いろいろ弄って読み込み画面を突破している
* もともと提供される情報が少ないので微妙

## Dockerで利用する
```
docker pull ghcr.io/amasecocoa/summaly-py
docker run -d --name summaly-proxy -p 8000:8000 -e PORT=3030 amasecocoasummaly-py
```

## サーバーを動作させる
レスポンスの速度を上げる場合はASGIサーバーはuvicornではなくRust製のASGIサーバーであるGranianを推奨しています。
```bash
granian --interface asgi pysummaly.server:app
```