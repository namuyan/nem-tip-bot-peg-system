#!/user/env python3
# -*- coding: utf-8 -*-

from web3 import Web3, HTTPProvider, IPCProvider
from config import NUKO_TO_WEI, LOCAL_IP_ADDRESS
from basic_fnc import bytes2hex
import logging
import time
try:
    import rlp
    from ethereum.transactions import Transaction
    self_sign_system = True
except:
    self_sign_system = False


class EtherInterface:
    def __init__(self, mycfg):
        self.config = mycfg
        while True:
            try:
                pair = mycfg.node.pop(0)
                logging.info("# node %s:%d" % pair)
                uri = "http://%s:%d" % pair
                self.web3 = Web3(HTTPProvider(uri))
                logging.info("# connect %s" % self.web3.eth.blockNumber)
                if self_sign_system:
                    self.send_to = self._sign_send
                else:
                    self.send_to = self._no_sign_send
                    assert pair[0] in LOCAL_IP_ADDRESS, "外部のGethに秘密鍵を送信する事は禁止されています。"
                logging.info("# self_sign_system %s" % self_sign_system)
                mycfg.node = pair
                return
            except Exception as e:
                logging.error(e)
                if len(mycfg.node) > 0:
                    continue
                else:
                    raise Exception("接続可能なノードが存在しません")

    def test(self):
        print(self.web3.eth.getBalance(self.config.account_pubkey))
        a = self.web3.eth.getTransactionsByAccount(self.config.account_pubkey)
        print(a)

    def check_address(self, address):
        return self.web3.isAddress(address)

    def get_block_by_number(self, number):
        return self.web3.eth.getBlock(number)

    def get_transaction_by_hash(self, tx_hash):
        return self.web3.eth.getTransaction(tx_hash)

    def send_to(self, to_address, amount, data=b''):
        pass

    def _sign_send(self, to_address, amount, data=b''):
        # 自前の署名機構を用いて送金
        nonce = self.web3.eth.getTransactionCount(self.config.account_pubkey)
        gas_price = self.web3.eth.gasPrice  # 常時4Gwei?
        tx = Transaction(
            nonce=nonce,
            gasprice=gas_price,
            startgas=21000,
            to=to_address,
            value=amount,
            data=data,
        )
        params = (to_address, amount / NUKO_TO_WEI, gas_price, nonce)
        logging.info("Send to=%s,amount=%s,price=%s,nonce=%s" % params)
        tx.sign(self.config.account_seckey)
        raw_tx_hex = self.web3.toHex(rlp.encode(tx))
        logging.info("raw tx:%s" % raw_tx_hex)
        try:
            tx_hash = bytes2hex(self.web3.eth.sendRawTransaction(raw_tx_hex))
            return True, tx_hash
        except ValueError as e:
            logging.error(e)
            return False, e

    def _no_sign_send(self, to_address, amount, data=b''):
        # gethの署名機構を用いて送金
        nonce = self.web3.eth.getTransactionCount(self.config.account_pubkey)
        gas_price = self.web3.eth.gasPrice
        transaction = {
            'to': to_address, 'value': amount,
            'gas': 21000, 'gasPrice': gas_price,
            'nonce': nonce, 'chainId': 1, 'data': data
        }
        params = (to_address, amount / NUKO_TO_WEI, data)
        logging.info("Send to=%s, amount=%s, data=%s" % params)
        signed = self.web3.eth.account.signTransaction(transaction, self.config.account_seckey)
        raw_tx_hex = bytes2hex(signed.rawTransaction)
        logging.info(raw_tx_hex)
        try:
            tx_hash = bytes2hex(self.web3.eth.sendRawTransaction(raw_tx_hex))
            return True, tx_hash
        except ValueError as e:
            logging.error(e)
            return False, e

    """def _no_sign_send2(self, to_address, amount, data=b''):
        # gethの署名機構を用いて送金
        transaction = {
            'from': self.config.account_pubkey, 'to': to_address,
            'value': amount, 'data': data
        }
        params = (to_address, amount / 1000000000000000000, data)
        logging.info("Send to=%s,amount=%s,data=%s" % params)
        tx = bytes2hex(self.web3.eth.sendTransaction(transaction))
        logging.info("txhash:%s" % tx)
        return tx"""