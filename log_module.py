#!/user/env python3
# -*- coding: utf-8 -*-

"""
ロギングモジュールの設定
"""

import logging
import logging.handlers


class MakeLogging:
    ws = None

    def __init__(self):
        # rootロガーを取得
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(levelname)-6s] [%(threadName)-10s] [%(asctime)-24s] %(message)s')  # %(levelname)s]
        self._logger = logger
        self._formatter = formatter

    def make_stream_handler(self):
        # sys.stderrへ出力するハンドラーを定義
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(self._formatter)
        self._logger.addHandler(sh)

    def make_file_handler(self):
        # 書き出し
        sh = logging.handlers.TimedRotatingFileHandler(
            filename='log/debug.log',
            when='D',
            backupCount=3
        )
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(self._formatter)
        self._logger.addHandler(sh)

    def make_socket_handler(self):
        # ログファイルをTCPソケット経由で出力するハンドラーを定義
        # WARNINGのSQLは出さない
        sh = logging.handlers.SocketHandler(host='localhost', port=12345)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(self._formatter)
        self._logger.addHandler(sh)


