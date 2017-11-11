#!/user/env python3
# -*- coding: utf-8 -*-

import falcon
import json
from wsgiref import simple_server
from twitter_lib import TwitterClass
from database import DataBase
from config import NUKO_TO_WEI, MICRO_TO_WEI
from datetime import datetime
import threading
import logging
import time
import os
import codecs
import base64
import copy

# text_code = "shift_jis" if os.name == 'nt' else "utf-8"
text_code = "utf-8"


def display(num, divi):
    """ 明示的に有効小数点を表示する """
    str_num = str(abs(num))
    str_dir = '-' if num < 0 else ''
    if divi > 30:
        raise Exception("too large!")
    elif len(str_num) <= divi:
        str_num = '0' * (divi - len(str_num) + 1) + str_num
    n = str_num[:-divi]
    m = str_num[-divi:]
    if divi == 0:
        return str(num)
    return "%s%s.%s" % (str_dir, n, m)


def unix2date(t):
    return datetime.fromtimestamp(t).strftime('%Y/%m/%d %H:%M')


class IndexPage(TwitterClass, DataBase):
    def __init__(self, mycfg):
        TwitterClass.__init__(self, mycfg=mycfg)
        DataBase.__init__(self, mycfg=mycfg)
        self.config = mycfg
        self.session = dict()
        self.session_time = dict()
        self.session_lock = threading.Lock()
        self.session_limit = 3600

    def on_get(self, req, resp, select_page):
        logging.info("page: %s" % select_page)
        session_id, session = self.start_session(req=req, resp=resp)
        resp.status = falcon.HTTP_200
        resp.content_type = 'text/html'

        if select_page not in ('favicon.ico', 'login.html', 'user.html', 'template.html', 'withdraw.html',
                               'throw.html'):
            # resp.status = falcon.HTTP_400
            # resp.body = "<p>not found page</p>"
            resp.status = falcon.HTTP_301
            resp.set_header('Location', './login.html')
        try:
            with codecs.open('./html/%s' % select_page, 'r', text_code) as f:
                params = self.get_params(req=req, resp=resp, select_page=select_page, session=session)
                page = f.read()
                resp.body = page % params
        except Exception as e:
            # import traceback
            # traceback.print_exc()
            logging.error(e)
            resp.status = falcon.HTTP_400
            resp.body = "<p>faild reading: %s</p>" % e
            resp.body += "<a href=\"./login.html\">login page</a>"

        self.finish_session(session_id=session_id, session=session)
        logging.debug("%s : %s" % (session_id, session))

    def get_params(self, req, resp, select_page, session):
        if select_page == 'index.html':
            pass
        elif select_page == 'login.html':
            redirect_url, oauth_token, oauth_token_secret = self.get_user_token()
            session['oauth_token'] = oauth_token
            session['oauth_token_secret'] = oauth_token_secret
            return redirect_url

        elif select_page == 'user.html':
            if 'screen' not in session:
                api = self.get_user_api_obj(oauth_token=session['oauth_token'],
                                            oauth_token_secret=session['oauth_token_secret'],
                                            oauth_verifier=req.get_param('oauth_verifier'))
                user_data = api.verify_credentials()
                # session['api'] = api
                session['screen'] = user_data.screen_name
                session['twitter_id'] = user_data.id
                session['user_id'] = self.twitter_to_user_id(session['twitter_id'], session['screen'])
                session['login_ip'] = req.remote_addr
                session['image'] = user_data.profile_image_url_https

            self.commit()
            deposit_balance = self.deposit_balance(user_id=session['user_id'], summary=True)
            withdraw_balance = self.withdraw_balance(user_id=session['user_id'], summary=True)
            inner_balance = self.inner_balance(user_id=session['user_id'], summary=True)
            total_balance = display(deposit_balance - withdraw_balance + inner_balance, 6)
            deposit_balance = display(deposit_balance, 6)
            withdraw_balance = display(withdraw_balance, 6)
            inner_balance = display(inner_balance, 6)

            tag_amount = display(session['user_id'], 18)
            tag_address = "<br>".join(self.get_tag_address(session['user_id']))
            inner_his = self.inner_balance(user_id=session['user_id'], summary=False)
            deposit_his = self.deposit_balance(user_id=session['user_id'], summary=False)
            withdraw_his = self.withdraw_balance(user_id=session['user_id'], summary=False)
            name = ["GOX", "outside"]
            inner_his = "\n".join([
                "<tr><td>%d</td><td>@%s</td><td>@%s</td><td>%s NUKO</td><td>%s</td></tr>" % (
                e['uuid'], self.user_to_screen(e['sender']), self.user_to_screen(e['recipient']),
                display(e['amount'], 6), unix2date(e['time'])) for e in inner_his])
            deposit_his = "\n".join([
                "<tr><td><a href='http://explorer.nekonium.org/tx/0x%s'>%d</a></td><td>0x%s</td>"
                "<td>%s NUKO</td><td>%s</td></tr>" % (e['tx_hash'], e['uuid'], e['address'],
                    display(e['amount'], 6), unix2date(e['time'])) for e in deposit_his])
            withdraw_his = "\n".join([
                "<tr><td><a href='http://explorer.nekonium.org/tx/0x%s'>%d</a></td><td>0x%s</td>"
                "<td>%s NUKO</td><td>%s</td></tr>" % (e['tx_hash'], e['uuid'], e['address'],
                display(e['amount'], 6), unix2date(e['time'])) for e in withdraw_his])
            oldest_uuid = self.get_oldest_uuid(session['user_id'])

            return (session['screen'], deposit_balance, withdraw_balance, inner_balance, total_balance,
                    tag_amount, self.config.account_pubkey, tag_address, oldest_uuid, inner_his,
                    deposit_his, withdraw_his)

        elif select_page == 'withdraw.html':
            if session['login_ip'] != req.remote_addr:
                return 'danger', 'danger!', 'Failed request IP is different from login IP!'
            if int(req.get_param('oldest_uuid')) != self.get_oldest_uuid(session['user_id']):
                return 'warning', 'Oh snap!', 'You may double clicked! %d' % req.get_param('oldest_uuid')

            with self.balance_lock:
                self.commit()
                address = req.get_param('address')
                amount_wei = round(round(float(req.get_param('amount')), 6) * NUKO_TO_WEI)
                if not self.obj.neko.check_address(address):
                    return 'warning', 'Oh snap!', 'Input address is not correct.'

                # 残高取得チェック
                deposit_balance = self.deposit_balance(user_id=session['user_id'], summary=True)
                withdraw_balance = self.withdraw_balance(user_id=session['user_id'], summary=True)
                inner_balance = self.inner_balance(user_id=session['user_id'], summary=True)
                fee_wei = 1000 * MICRO_TO_WEI  # 0.001 NUKO
                total_wei = round((deposit_balance - withdraw_balance + inner_balance) * MICRO_TO_WEI)
                if amount_wei > total_wei + fee_wei:
                    return 'warning', 'Oh snap!', 'You tried to bring more than available balance.'

                # 送金実行
                ok, tx_hash = self.obj.neko.send_to(to_address=address, amount=amount_wei)
                if not ok:
                    return 'warning', 'Oh snap!', 'Failed sending because %s' % tx_hash

                # DBへ書き込み
                try:
                    with self.connect.cursor() as cursor:
                        sql = "INSERT INTO `outgoing` SET `tx_hash`=%s,`address`='%s',`sender`='%d'," \
                              "`amount`='%d',`height`='0',`time`='%d'"
                        send_micro = round((amount_wei+fee_wei) / MICRO_TO_WEI)
                        cursor.execute(sql % (tx_hash, address, session['user_id'], send_micro, int(time.time())))
                    self.commit()
                except Exception as e:
                    self.rollback()
                    logging.error(e)

            # TX取り込まれるのを確認
            threading.Thread(
                target=self._confirm_transaction, args=(tx_hash,), name="chk %s" % tx_hash[2:6], daemon=True
            ).start()

            return ('success', 'Well done!',
                    'txhash: <a href="http://explorer.nekonium.org/tx/{0}">{0}</a>'.format(tx_hash))

        elif select_page == 'throw.html':
            # nekopeg本体より引き出す
            if 'screen' not in session:
                return "warning", "stop!", "You are not login!"
            if session['login_ip'] != req.remote_addr:
                return "danger", "danger!", 'Failed request IP is different from login IP!'

            now = int(time.time())
            amount_tipnem = round(float(req.get_param('amount')) * 10**1)
            amount_micro = round(float(req.get_param('amount')) * 10**6)

            with self.balance_lock:
                self.commit()
                # 残高チェック(nekopeg内)
                deposit_balance = self.deposit_balance(user_id=session['user_id'], summary=True)
                withdraw_balance = self.withdraw_balance(user_id=session['user_id'], summary=True)
                inner_balance = self.inner_balance(user_id=session['user_id'], summary=True)
                total_micro = deposit_balance - withdraw_balance + inner_balance
                if total_micro < amount_micro:
                    return "warning", "stop!", "You don't have enough balance."

                # 残高チェック(nekopeg外)
                tipbot_raw = self.get_tipbot_balance()
                tipbot_micro = round(tipbot_raw * 10**6 / 10)
                if tipbot_micro < amount_micro:
                    return "warning", "stop!", "Don't have enough token in this system. " \
                                               "available %s NUKO" % display(tipbot_raw, 1)

                data = {
                    "sender": "@" + self.config.screen,
                    "recipient": "@" + session['screen'],
                    "mosaic": "namuyan:nekonium",
                    "amount": amount_tipnem,
                    "txt": "Nekonium pegtoken system",
                    "announce": True
                }
                ok, result = self.obj.tip.request(command='account/throw', data=data)
                if not ok:
                    return "warning", "Tipnem error: ", result
                uuid = result['uuid']
                controller_id = 1

                with self.connect.cursor() as cursor:
                    sql = "INSERT INTO `inner_transaction` SET `uuid`='%d',`sender`='%d'," \
                          "`recipient`='%d',`amount`='%d',`time`='%d'"
                    cursor.execute(sql % (uuid, session['user_id'], controller_id, amount_micro, now))
                self.commit()
            return "success", "Success!", "converted, check with xembook!"

        elif select_page == 'template.html':
            pass
        else:
            pass

    def _confirm_transaction(self, tx_hash):
        count = 0
        while count < 100:
            time.sleep(10)
            tx = self.obj.neko.get_transaction_by_hash(tx_hash=tx_hash)
            if tx.blockNumber is None:
                continue
            else:
                with self.connect.cursor() as cursor:
                    sql = "UPDATE `outgoing` SET `height`='%d' WHERE `tx_hash`=%s"
                    cursor.execute(sql % (tx.blockNumber, tx_hash))
                self.commit()
                logging.info("finish")
                break
        else:
            logging.error("failed %s" % tx_hash)

    def start_session(self, req, resp):
        with self.session_lock:
            cookies = req.cookies
            if "session_id" in cookies:
                session_id = cookies['session_id']
                if session_id in self.session_time and self.session_time[session_id] < time.time():
                    # セッション切れ
                    self.session[session_id] = dict()
                    logging.info("despaired session %s" % session_id)
                    return session_id, dict()
                elif session_id in self.session:
                    logging.info("find session %s" % session_id)
                    return session_id, copy.deepcopy(self.session[session_id])

            session_id = base64.b64encode(os.urandom(24)).decode()
            resp.set_cookie('session_id', session_id, max_age=self.session_limit, secure=False)
            self.session[session_id] = dict()
            logging.info("create session %s" % session_id)
            return session_id, dict()

    def finish_session(self, session_id, session):
        with self.session_lock:
            now = int(time.time())
            self.session[session_id] = session
            self.session_time[session_id] = now + self.session_limit
            self.session = {k: self.session[k] for k in self.session if self.session_time[k] > now}
            logging.info("close session %s" % session_id)

    def get_tipbot_balance(self):
        ok, result = self.obj.tip.request(command='account/balance', data='')
        if not ok:
            logging.error(result)
            return 0
        return result['all']['namuyan:nekonium'] if 'namuyan:nekonium' in result['all'] else 0


class RestApi(threading.Thread):
    def __init__(self, mycfg):
        super().__init__(name="rest", daemon=True)
        self.config = mycfg

    def run(self):
        app = falcon.API()
        index_page = IndexPage(mycfg=self.config)
        index_page.obj = self.obj
        app.add_route("/{select_page}", index_page)
        port = 8000
        httpd = simple_server.make_server(self.config.rest_host, port, app)
        logging.info("# REST start")
        httpd.serve_forever()