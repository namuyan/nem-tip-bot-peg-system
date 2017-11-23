#!/user/env python3
# -*- coding: utf-8 -*-


import pymysql.cursors
import logging
import time
import threading
import random

INT_MAX = 2147483647

"""使い方
try:
    with connection.cursor() as cursor:
        sql = "INSERT INTO `users` (`email`, `password`) VALUES (%s, %s)"
        cursor.execute(sql, ('webmaster@python.org', 'very-secret'))

    # connection is not autocommit by default. So you must commit to save
    # your changes.
    connection.commit()

    with connection.cursor() as cursor:
        # Read a single record
        sql = "SELECT `id`, `password` FROM `users` WHERE `email`=%s"
        cursor.execute(sql, ('webmaster@python.org',))
        result = cursor.fetchone()
        print(result)
finally:
    connection.close()
"""


class DataBase:
    def __init__(self, mycfg):
        self.config = mycfg
        self.connect = self.create_connection()
        self.balance_lock = threading.Lock()

    def create_connection(self):
        count = 1
        while True:
            try:
                connect = pymysql.connect(
                    host=self.config.db['host'], user=self.config.db['user'],
                    password=self.config.db['pass'], db=self.config.db['db'],
                    charset=self.config.db['charset'],
                    cursorclass=pymysql.cursors.DictCursor
                )
                # Enforce UTF-8 for the connection.
                connect.set_charset('utf8mb4')
                with connect.cursor() as cursor:
                    cursor.execute('SET NAMES utf8mb4')
                    cursor.execute("SET CHARACTER SET utf8mb4")
                    cursor.execute("SET character_set_connection=utf8mb4")
                connect.commit()
                logging.debug("# db connect!")
                self.polling()
                return connect

            except Exception as e:
                logging.error(e)
                time.sleep(20)
                logging.debug("BD connect retry %d" % count)
                count += 1

    def tmp_check(self):
        with self.connect.cursor() as cursor:
            print("ok")

    def get_oldest_uuid(self, user_id):
        with self.connect.cursor() as cursor:
            sql = "SELECT MAX(`uuid`) AS 'uuid' FROM `outgoing` WHERE `sender`='%d' LIMIT 1"
            cursor.execute(sql % user_id)
            data = cursor.fetchone()
            if data:
                return 0
            return data['uuid']

    def get_tag_address(self, user_id):
        with self.connect.cursor() as cursor:
            sql = "SELECT `address` FROM `bind_address` WHERE `user_id`='%d'"
            cursor.execute(sql % user_id)
            data = cursor.fetchall()
            if data:
                return (a['address'] for a in data)
            else:
                return tuple()

    def deposit_balance(self, user_id, summary=True):
        with self.connect.cursor() as cursor:
            sql = "SELECT `uuid`,LOWER(HEX(`tx_hash`)) AS 'tx_hash',`address`,`amount`,`height`,`time`" \
                  " FROM `incoming` WHERE `recipient`='%d' ORDER BY `uuid` DESC"
            cursor.execute(sql % user_id)
            data = cursor.fetchall()
            if not summary:
                return data if data else []
            elif data is None:
                return 0
            else:
                return sum([n['amount'] for n in data])

    def withdraw_balance(self, user_id, summary=True):
        with self.connect.cursor() as cursor:
            sql = "SELECT `uuid`,LOWER(HEX(`tx_hash`)) AS 'tx_hash',`address`,`sender`," \
                  "`amount`,`type`,`height`,`time` FROM `outgoing` WHERE `sender`='%d' " \
                  " ORDER BY `uuid` DESC"
            cursor.execute(sql % user_id)
            data = cursor.fetchall()
            if not summary:
                return data if data else []
            elif data is None:
                return 0
            else:
                return sum([n['amount'] for n in data])

    def inner_balance(self, user_id, summary=True):
        with self.connect.cursor() as cursor:
            sql = "SELECT `uuid`,`sender`,`recipient`,`amount`,`time` FROM `inner_transaction` " \
                  "WHERE `sender`='%d' OR `recipient`='%d' ORDER BY `uuid` DESC"
            cursor.execute(sql % (user_id, user_id))
            data = cursor.fetchall()
            if not summary:
                return data if data else []
            elif data is None:
                return 0
            else:
                send = sum([n['amount'] for n in data if n['sender'] == user_id])
                receive = sum([n['amount'] for n in data if n['recipient'] == user_id])
                return receive - send

    def user_to_twitter_id(self, user_id):
        with self.connect.cursor() as cursor:
            sql = "SELECT `twitter_id` FROM `bind_user` WHERE `user_id`='%d'"
            cursor.execute(sql % user_id)
            try:
                return cursor.fetchone()['twitter_id']
            except:
                return None

    def twitter_to_user_id(self, twitter_id, screen, commit=True):
        with self.connect.cursor() as cursor:
            sql = "SELECT `user_id`,`screen` FROM `bind_user` WHERE `twitter_id`='%d'"
            cursor.execute(sql % twitter_id)
            data = cursor.fetchone()
            if data is not None and screen == data['screen']:
                return data['user_id']
            elif data is not None:
                sql = "UPDATE `bind_user` SET `screen`='%s' WHERE `twitter_id`='%d'"
                cursor.execute(sql % (screen, twitter_id))
                if commit:
                    self.commit()
                return data['user_id']
            else:
                user_id = random.randint(INT_MAX // 10, INT_MAX)
                sql = "INSERT INTO `bind_user` SET `user_id`='%d',`twitter_id`='%d',`screen`='%s',`time`='%d'"
                cursor.execute(sql % (user_id, twitter_id, self.escape_str(screen), int(time.time())))
                self.commit()
                return user_id

    def user_to_screen(self, user_id):
        controller_list = {0: "Mr.GOX", 1: "Mr.outsider"}
        if user_id in controller_list:
            return controller_list[user_id]
        else:
            with self.connect.cursor() as cursor:
                sql = "SELECT `screen` FROM `bind_user` WHERE `user_id`='%d'"
                cursor.execute(sql % user_id)
                data = cursor.fetchone()
                if data:
                    return data['screen']
                return 'unknown?'

    def add_deposit_permission(self, user_id):
        with self.connect.cursor() as cursor:
            sql = "UPDATE `bind_user` SET `deposit_permission`='1' WHERE `user_id`='%d'"
            cursor.execute(sql % user_id)
        self.commit()

    def deposit_permission(self, user_id):
        with self.connect.cursor() as cursor:
            sql = "SELECT `deposit_permission` FROM `bind_user` WHERE `user_id`='%d'"
            cursor.execute(sql % user_id)
            data = cursor.fetchone()
            if data:
                return bool(data['deposit_permission'])
            return False

    def get_cursor(self):
        self.cursor = self.connect.cursor()
        # self.cursor.fetchall()
        # self.cursor.fetchone()

    def execute(self, sql):
        logging.debug(sql)
        self.cursor.execute(sql)

    def execute_escape(self, sql, params):
        logging.debug(sql + " " + str(params))
        self.cursor.execute(sql, params)

    def commit(self):
        try:
            self.connect.commit()
        except pymysql.err.OperationalError as e:
            logging.error(e)
            if e.find("Lost connection to MySQL server during query") != -1:
                self.connect = self.create_connection()
                raise Exception("# I reconnect please retry!")

    def rollback(self):
        self.connect.rollback()

    @staticmethod
    def get_last_id(cursor):
        cursor.execute("SELECT LAST_INSERT_ID()")
        return cursor.getline()['LAST_INSERT_ID()']

    @staticmethod
    def escape_str(string):
        try:
            return string.replace('\'', '’').replace('`', '‘')
        except:
            return None

    def polling(self):
        # commitを使用しなくてもコネクション維持できるのか？
        def _polling():
            with self.connect.cursor() as cursor:
                cursor.execute("SHOW TABLES")
        threading.Timer(3600, _polling).start()
