#!/user/env python3
# -*- coding: utf-8 -*-


import logging
from database import DataBase

database_dict = {
    'incoming': [
        'uuid INT UNSIGNED NOT NULL AUTO_INCREMENT',
        'tx_hash BINARY(32) NOT NULL',
        'address CHAR(255) NOT NULL',
        'recipient INT NOT NULL',
        'amount BIGINT UNSIGNED NOT NULL',
        'height INT NOT NULL',
        'time INT UNSIGNED NOT NULL',
        'PRIMARY KEY (uuid)'
    ],
    "outgoing": [
        'uuid INT UNSIGNED NOT NULL AUTO_INCREMENT',
        'tx_hash BINARY(32) NOT NULL',
        'address VARCHAR(255) NOT NULL',
        'sender INT NOT NULL',
        'amount BIGINT UNSIGNED NOT NULL',
        'type TINYINT DEFAULT 0',  # 0=
        'height INT',
        'time INT UNSIGNED',
        'PRIMARY KEY (uuid)'
    ],
    "inner_transaction": [
        'uuid INT UNSIGNED NOT NULL',
        'sender INT NOT NULL',
        'recipient INT NOT NULL',
        'amount BIGINT UNSIGNED NOT NULL',
        'time INT UNSIGNED',
        'PRIMARY KEY (uuid)'
    ],
    "bind_user": [
        'user_id INT UNSIGNED NOT NULL',
        'twitter_id BIGINT UNSIGNED NOT NULL',
        'screen VARCHAR(255)',
        'time INT UNSIGNED',
        'PRIMARY KEY (user_id)'
    ],
    "bind_address": [
        'address VARCHAR(128) NOT NULL',
        'user_id INT UNSIGNED',
        'time INT UNSIGNED',
        'PRIMARY KEY (address)'
    ]
}

index_dict = {
    "incoming": [
        "tx_hash",
        "address",
        "recipient"
    ],
    "outgoing": [
        "tx_hash",
        "address",
        "sender",
    ],
    "inner_transaction": [
        "sender",
        "recipient"
    ]
}


class Init(DataBase):
    def __init__(self, mycfg):
        super().__init__(mycfg=mycfg)
        self.get_cursor()

    def check(self):
        self.check_db_exist()
        self.commit()

    def close(self):
        self.cursor.close()
        self.connect.close()

    def check_db_exist(self):
        self.execute("SHOW TABLES")
        exist_tables = {list(n.values())[0] for n in self.cursor.fetchall()}
        logging.debug("exist %s" % exist_tables)

        all_tables = set(database_dict.keys())
        logging.debug("all %s" % all_tables)

        for name in all_tables:
            if name in exist_tables:
                continue
            sql = "CREATE TABLE `%s` (" % name
            sql += ",".join(database_dict[name])
            sql += ")"
            self.execute(sql)

    def check_db_index(self):
        for name in index_dict:
            sql = "SHOW INDEX FROM `%s`" % name
            self.execute(sql)
            all_indexes = {n["Column_name"] for n in self.cursor.fetchall()}

            for index_col in index_dict[name]:
                if index_col in all_indexes:
                    continue
                sql = "ALTER TABLE %s ADD INDEX %s(%s)"
                index_name = "%s_idx" % index_col
                self.execute_escape(sql, (name, index_name, index_col))
        return


