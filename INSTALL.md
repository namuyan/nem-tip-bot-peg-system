インストール方法
===============


#### 基本
* `pip install git+https://github.com/pipermerriam/web3.py.git`
* `pip install PyMySQL`
* `pip install msgpack-python`
* `pip install falcon`
* `pip install websocket-client`
* config.py.tmp => config.py にリネーム


#### 外部のGethを用いるための署名機構(Linux専用)
* `pip install ethereum`


#### DBアカウント作成
* `mysql -u root -p`
* `CREATE USER 'peg'@'localhost' IDENTIFIED BY 'Q3h5GP';`
* `CREATE DATABASE pegger CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;`
* `GRANT all privileges ON pegger.* TO 'peg'@'localhost';`
* `exit`


