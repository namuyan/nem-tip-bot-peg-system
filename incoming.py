#!/user/env python3
# -*- coding: utf-8 -*-


from config import MICRO_TO_WEI, NUKO_TO_WEI, LOCAL_IP_ADDRESS
from database import DataBase
from basic_fnc import bytes2hex
import time
import threading
import logging
import os.path
import copy
import pymysql


class IncomingPolling(DataBase):
    def __init__(self, mycfg):
        super().__init__(mycfg=mycfg)
        self.config = mycfg
        self.now_height = 0
        self.finish = 0
        self.obj = None

    def start(self):
        get_genesis = bytes2hex(self.obj.neko.get_block_by_number(0).hash)
        if get_genesis != self.config.genesis:
            logging.error("# don't match %s != %s" % (get_genesis, self.config.genesis))

        threading.Thread(
            target=self._run, name="incoming", daemon=True
        ).start()
        logging.info("# incoming start")

    def _run(self):
        time_span = 0.02 if self.config.node[0] in LOCAL_IP_ADDRESS else 0.1
        divide = 1500
        error = count = announce = 0
        block_data = self.read_block_file()
        logging.info("# start income loop %ssec %sdiv" % (time_span, divide))

        while error < 50:
            try:
                time.sleep(time_span)
                count += 1
                if self.config.stop_signal:
                    break

                previous_height = max(block_data)
                next_height = previous_height + 1
                block = self.obj.neko.get_block_by_number(next_height)
                if block is None:
                    if time_span != 5:
                        logging.info("# finish sync %s" % next_height)
                        time_span = 5
                        divide = 800
                        self.finish = 1
                    continue
                next_block_hash = bytes2hex(block.hash)
                previous_block_hash = bytes2hex(block.parentHash)

                if block_data[previous_height] == previous_block_hash:
                    # 新規Blockとして追加
                    block_data[next_height] = next_block_hash
                    self.now_height = next_height
                    if announce:
                        logging.info("new block %d" % next_height)
                    # TXにユーザーバインドアドレスが含まれていないかチェック
                    txs = [
                        self.obj.neko.get_transaction_by_hash(bytes2hex(tx))
                        for tx in block.transactions
                    ]
                    self.recode_txs(txs, block, announce)

                else:
                    # フォークによりBlockを一つ前へ...
                    del block_data[previous_height]
                    with self.connect.cursor() as cursor:
                        sql = "DELETE FROM `incoming` WHERE `height`='%d'"
                        cursor.execute(sql % block.number)
                    self.commit()
                    logging.info("find fork %s" % previous_height)
                    continue

                if count % divide == 0:
                    error = 0
                    logging.info("# block write %d" % next_height)
                    threading.Thread(
                        target=self.write_block_file, args=(copy.copy(block_data),), name="block write", daemon=True
                    ).start()

            except ValueError as e:
                self.rollback()
                logging.error(e)
                error += 1

            except Exception as e:
                self.rollback()
                logging.error(e)
                import traceback
                traceback.print_exc()
                error += 1

        self.write_block_file(block_data)
        logging.error("# incoming polling stopped")
        self.config.stop_ok.append("incoming")

    def recode_txs(self, txs, block, announce):
        with self.connect.cursor() as cursor:
            for tx in txs:
                try:
                    if tx.to != self.config.account_pubkey:
                        continue
                    address_from = dict(tx)['from']
                    tx_hash = bytes2hex(tx.hash)

                    # 既に登録されているTXか確認
                    sql = "SELECT `uuid` FROM `incoming` WHERE `tx_hash`=%s"
                    cursor.execute(sql % tx_hash)
                    if cursor.fetchone() is not None:
                        continue
                    logging.info("# TX:%s" % tx_hash)
                    logging.info("# ADDR:%s" % address_from)

                    # bind_userによるアドレス定義
                    sql = "SELECT `user_id` FROM `bind_user` WHERE `user_id`= '%d'"
                    cursor.execute(sql % tx.value)
                    user_id = cursor.fetchone()
                    if user_id:
                        params = (
                            address_from,
                            user_id['user_id'],
                            block.timestamp
                        )
                        sql = "INSERT INTO `bind_address` (`address`,`user_id`,`time`) VALUES ('%s','%d','%d')"
                        cursor.execute(sql % params)
                        # ダブればここでエラーになる
                        logging.info("# bind user %s=%s" % (user_id['user_id'], address_from))
                        sql = "UPDATE `incoming` SET `recipient`='%d' WHERE `address`='%s' AND `recipient`='0'"
                        cursor.execute(sql % (user_id['user_id'], address_from))
                        continue

                    # bind_addressによる入金
                    sql = "SELECT `user_id` FROM `bind_address` WHERE `address`='%s'"
                    cursor.execute(sql % address_from)
                    user_id = cursor.fetchone()
                    user_id = 0 if user_id is None else user_id['user_id']
                    logging.info("# bind address %s=%s" % (user_id, address_from))
                    params = (
                        tx_hash, address_from,
                        user_id, round(tx.value / MICRO_TO_WEI),
                        tx.blockNumber, block.timestamp
                    )
                    sql = "INSERT INTO `incoming` (`tx_hash`,`address`,`recipient`,`amount`," \
                          "`height`, `time`) VALUES (%s,'%s','%d','%d','%d','%d')"
                    cursor.execute(sql % params)
                    logging.info("# income %s <= %s" % (user_id, round(tx.value / NUKO_TO_WEI, 6)))

                except pymysql.err.IntegrityError as e:
                    logging.error(e)
                    continue
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    logging.error(e)
                    continue

        self.commit()
        return

    @staticmethod
    def write_block_file(data):
        file = './tmp/block.csv'
        height = max(data)
        f = open(file, 'w')
        data = [str(b) + ',' + data[b] for b in data]
        f.write("\n".join(data))
        f.close()
        logging.info("# write finish %s" % height)

    def read_block_file(self):
        file = './tmp/block.csv'
        if os.path.exists(file):
            f = open(file, 'r')
            data = f.read().split("\n")
            data = {int(d.split(",", 1)[0]): d.split(",")[1] for d in data}
            f.close()
            return data
        else:
            f = open(file, 'w')
            # block.info
            # [block number], [block hash], [tx num], [txs]
            f.write('0,%s' % self.config.genesis)
            f.close()
            return {0: self.config.genesis}
