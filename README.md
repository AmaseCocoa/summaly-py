# summaly-py
misskey-dev/summalyのPython実装。

<!--クライアント部分はpysummaryとしてPyPIからインストールできます。-->

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