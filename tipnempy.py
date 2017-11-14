#!/user/env python3
# -*- coding: utf-8 -*-

from ed25519 import Ed25519
import websocket
import threading
import queue
import logging
import time
import json
import random

"""
Tipnemを扱うライブラリ
2017/11/07
"""

version = "1.2"
author = "namuyan"


class WebSocketClient:
    timeout = 60
    result = dict()
    result_lock = threading.Lock()
    streaming_que = queue.LifoQueue(maxsize=1000)
    user_code = None
    height = 0

    def __init__(self, url, test=False):
        self.url = url
        self.test = test
        self.ws = None

    def _create_connect(self):
        retry = 0
        while True:
            try:
                retry += 1
                websocket.enableTrace(self.test)
                ws = websocket.WebSocketApp(self.url)
                ws.on_message = self.on_message
                ws.on_close = self.on_error
                ws.on_open = self.on_open
                ws.on_error = self.on_error
                ws.run_forever()
            except Exception as e:
                logging.error(e)
                logging.error("# retry connect to tipnem after 180s, %s" % retry)
                time.sleep(180)

    def login_by_key(self, seckey, pubkey, screen):
        sign = Ed25519.sign(message=self.user_code, secret_key=seckey, public_key=pubkey)
        data = {
            "screen_name": "@" + screen,
            "sign": sign.decode()
        }
        ok, result = self.request(command="user/pubkey/login", data=data)
        if not ok:
            logging.error("pubkey login %s" % result)
            return False
        if result['level'] > 0:
            logging.info("# auto login! level %d" % result['level'])
            return True
        return False

    def login_by_pin(self, screen):
        while True:
            print()
            data = {"screen_name": screen}
            ok, result = self.request(command="user/offer", data=data)
            if not ok and result != "pincode has been already created.":
                print("# failed login: ", result)
                continue

            pin_code = input("pincode >> ")
            data = {"screen_name": screen, "pincode": int(pin_code)}
            ok, result = self.request(command="user/check", data=data)
            if not ok:
                print("# failed login: ", result)
                continue

            print("# login OK!")

    def start(self, name="tipnem"):
        threading.Thread(
            target=self._create_connect, name=name, daemon=True
        ).start()
        while self.ws is None:
            time.sleep(0.2)
        logging.info("# create ws connection")

    def blocking(self, uuid):
        time_span = 0.005  # 1mS
        for c in range(int(self.timeout / time_span)):
            time.sleep(time_span)
            with self.result_lock:
                if uuid not in self.result:
                    continue
                else:
                    data = self.result[uuid]
                    del (self.result[uuid])
                return data['result'], data
        else:
            raise TimeoutError("UUID [%s]" % uuid)

    def request(self, command, data=None, blocking=True):
        uuid = random.randint(1, 2147483647)
        message = {
           "command": command,
           "data": data,
           "uuid": uuid
        }
        logging.debug("id:%d,msg:%s" % (uuid, message))
        self.ws.send(json.dumps(message))
        if blocking is False:
            return uuid

        time_span = 0.005  # 1mS
        for c in range(int(self.timeout / time_span)):
            time.sleep(time_span)
            if uuid not in self.result:
                continue
            else:
                with self.result_lock:
                    r = self.result[uuid]
                    del(self.result[uuid])
                    return r['result'], r['data']

        logging.error("result: %s" % self.result)
        raise TimeoutError("timeout [%s] [%s] [%s]" % (uuid, command, data))

    """ request """
    @staticmethod
    def check_key(keys, data):
        for k in keys:
            if k not in data:
                return False
        else:
            return True

    def on_message(self, ws, message):
        logging.debug("msg: %s" % message)
        try:
            data = json.loads(message)
        except Exception as e:
            logging.error(e)
            return
        if self.check_key(('level', 'user_code'), data):
            self.user_code = data['user_code']
            return

        elif self.check_key(('type', 'command'), data):
            if data['type'] == 'streaming':
                try:
                    item = (data['command'], data['data'], data['time'])
                    self.streaming_que.put_nowait(item=item)
                except queue.Full:
                    pass
                except Exception as e:
                    logging.error(e)
                    import traceback
                    traceback.print_exc()

            elif data['type'] == 'request':
                with self.result_lock:
                    self.result[data['uuid']] = data

            else:
                raise Exception("unknown type '%s'" % data['type'])
            return

        else:
            raise Exception("none...")

    def on_error(self, ws, error):
        logging.error("error: %s" % error)
        self.ws.close()

    def on_close(self, ws):
        logging.info("close: %s" % ws)
        # self.ws.close()
        # time.sleep(5)
        # logging.info("try reconnect")
        # self.create_connect()

    def on_open(self, ws):
        self.ws = ws
        logging.info("open: %s" % ws)


def test():
    """ テストコード """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)-6s] [%(threadName)-10s] [%(asctime)-24s] %(message)s')
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    ws = WebSocketClient(url="ws://153.122.86.46:8088")
    ws.start()
    ws.login_by_pin(screen=input("screen >> "))

    while True:
        try:
            print()
            command = input("cmd >> ")
            data = json.loads(input("data >> "))
            ok, result = ws.request(command=command, data=data)
            print(ok)
            print(result)
        except Exception as e:
            print("Error", e)

if __name__ == '__main__':
    test()
