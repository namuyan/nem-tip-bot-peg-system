#!/user/env python3
# -*- coding: utf-8 -*-


from tipnempy import WebSocketClient
from database import DataBase
from twitter_lib import TwitterClass
import threading
import logging
import time


class TipnemControl(WebSocketClient, DataBase, TwitterClass):
    def __init__(self, mycfg):
        WebSocketClient.__init__(self, url=mycfg.ws_host)
        DataBase.__init__(self, mycfg=mycfg)
        TwitterClass.__init__(self, mycfg=mycfg)
        self.on_nis_block = self.nis_block
        self.on_tip_receive = self.tip_receive
        self.config = mycfg
        self.finish = 0

    # over write
    def nis_block(self, ws, data):
        logging.info(list(data.values()))

    # over write
    def tip_receive(self, ws, data):
        logging.info(list(data.values()))
        if data['recipient'] != "@" + self.config.screen:
            return
        if data['mosaic'] != "namuyan:nekonium":
            return

        try:  # 残高を確定させる
            ok, result = self.request(command='account/history/check', data={'uuid': data['uuid']})
            if not ok:
                logging.error(result)
                return

        except Exception as e:
            logging.error("failed 'account/history/check' %s" % e)
            logging.error(data)
            return



        try:
            amount_micro = round(data['amount'] * 10 ** 6 / 10)
            user_data = self.get_user_data(screen=data['sender'][1:])
            twitter_id = user_data.id
            user_id = self.twitter_to_user_id(twitter_id, user_data.screen_name)
            controller_id = 1  # 外部は１

            with self.connect.cursor() as cursor:
                sql = "INSERT INTO `inner_transaction` SET `uuid`='%d',`sender`='%d',`recipient`='%d'," \
                      "`amount`='%d',`time`='%d'"
                params = (data['uuid'], controller_id, user_id, amount_micro, data['time'])
                cursor.execute(sql % params)
            self.commit()
        except Exception as e:
            logging.error("failed record %s" % e)
            logging.error(data)
            return

        logging.info("# throwed from id:%d" % data['uuid'])
        return

    def _control(self):
        history = self.get_all_history()
        uuid_set_tipnem = set(history.keys())
        screen = "@" + self.config.screen
        controller_id = 1  # Tipnem内の出入金は１

        self.commit()
        with self.connect.cursor() as cursor:
            sql = "SELECT `uuid` FROM `inner_transaction` WHERE `sender`='%d' OR `recipient`='%d'"
            cursor.execute(sql % (controller_id, controller_id))
            data = cursor.fetchall()
        uuid_set_db = {n['uuid'] for n in data}

        with self.connect.cursor() as cursor:
            sql = "INSERT INTO `inner_transaction` (`uuid`,`sender`,`recipient`,`amount`,`time`) VALUES"
            for uuid in uuid_set_tipnem - uuid_set_db:
                # 残高を確定させる
                ok, result = self.request(command='account/history/check', data={'uuid': uuid})
                if not ok:
                    logging.error(result)
                    # continue

                his = history[uuid]
                if his['mosaic_name'] != 'namuyan:nekonium':
                    continue
                # senderとrecipientを逆にする事に注意する
                if his['sender'] == screen:
                    recipient_id = 1
                else:
                    user_data = self.get_user_data(screen=his['sender'][1:])
                    recipient_id = self.twitter_to_user_id(user_data.id, user_data.screen_name)
                if his['recipient'] == screen:
                    sender_id = 1
                else:
                    user_data = self.get_user_data(screen=his['recipient'][1:])
                    sender_id = self.twitter_to_user_id(user_data.id, user_data.screen_name)

                amount_micro = round(his['amount'] / 10 * 10**6)
                insert = " ('%d','%d','%d','%d','%d')" % (uuid, sender_id, recipient_id, amount_micro, his['time'])
                try:
                    cursor.execute(sql + insert)
                except Exception as e:
                    logging.error(e)
                    continue
        self.commit()

        self.finish = 1
        logging.info("finish %s" % (uuid_set_tipnem - uuid_set_db))

        # 今の所予定のないループ
        while True:
            time.sleep(30)

    def get_all_history(self):
        uuid = None
        history = dict()
        while True:
            time.sleep(0.1)
            data = dict()
            if uuid:
                data['uuid'] = uuid
            ok, result = self.request(command='account/history', data=data)
            if not ok:
                break
            if len(result) == 0:
                return history
            history.update({
                 r['uuid']: r for r in result
            })
            uuid = result[-1:][0]['uuid']
            continue
        else:
            logging.error("# failed get all history")

    def start_control(self, name="control"):
        while True:
            time.sleep(10)
            if self.obj.income.finish == 1:
                break
            logging.debug("# wait incoming finish...")

        self.start()
        if not self.make_connection_with_console():
            logging.error("# failed login!")
            self.config.stop_signal = True
            return
        else:
            threading.Thread(
                target=self._control, name=name, daemon=True
            ).start()
            logging.info("# start control thread")

    def make_connection_with_console(self):
        retry = 0
        screen = "@" + self.config.screen
        while retry < 8:
            time.sleep(0.1)
            retry += 1
            ok, result = self.request(command="user/offer", data={"screen_name": screen})
            if not ok and result != "pincode has been already created.":
                logging.error("# failed %s" % result)
                continue
            while True:
                time.sleep(0.1)
                pin_code = input("pincode1 >> ")
                if len(pin_code) != 4:
                    logging.error("# retry")
                    continue
                break
            data = {"screen_name": screen, "pincode": pin_code}
            ok, result = self.request(command="user/check", data=data)
            if not ok:
                logging.error("failed %s" % result)
                continue

            logging.info("# login success")
            while retry < 8:
                time.sleep(0.1)
                retry += 1
                ok, result = self.request(command="user/upgrade", data="")
                if not ok:
                    logging.error("failed %s" % result)
                    continue
                pin_code = input("pincode2 >> ")
                ok, result = self.request(command="user/check", data={"pincode": pin_code})
                if not ok:
                    logging.error("failed %s" % result)
                    continue
                logging.info("# upgrade success")
                return True
        return False
