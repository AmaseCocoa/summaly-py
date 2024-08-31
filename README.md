# summaly-py
misskey-dev/summalyのPython実装。

クライアント部分はpysummaryとしてPyPIからインストールできます。

## サーバーを動作させる
レスポンスの速度を上げる場合はASGIサーバーはuvicornではなくRust製のASGIサーバーであるGranianを推奨しています。
```bash
granian --interface asgi pysummaly.server:app
```