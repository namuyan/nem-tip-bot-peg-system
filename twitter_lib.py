#!/user/env python3
# -*- coding: utf-8 -*-

import json
import tweepy
import time
import logging
import re
import threading
import random


logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
logging.getLogger("oauthlib").setLevel(logging.WARNING)
logging.getLogger("tweepy").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class TwitterClass:
    def __init__(self, mycfg):
        auth = tweepy.OAuthHandler(mycfg.twitter['consumer_key'], mycfg.twitter['consumer_secret'])
        auth.set_access_token(mycfg.twitter['access_token'], mycfg.twitter['access_token_secret'])
        self.config = mycfg
        self.auth = auth
        self.twi = tweepy.API(auth)
        # print("\n".join([key for key in logging.Logger.manager.loggerDict]))

        # キャッシュ
        self.get_user_cashe = dict()
        self.update_status_limit = list()
        self.update_status_fav_mode = 0

        self.screen = mycfg.screen

        # check access
        self.selfcheck_twitter()

    def get_user_token(self):
        auth = tweepy.OAuthHandler(self.config.twitter['consumer_key'],
                                   self.config.twitter['consumer_secret'], self.config.twitter['callback'])
        try:
            redirect_url = auth.get_authorization_url()
            request_token = auth.request_token
            return redirect_url, request_token['oauth_token'], request_token['oauth_token_secret']
        except tweepy.TweepError as e:
            logging.error(e.reason)
            raise Exception(e.reason)

    def get_user_api_obj(self, oauth_token, oauth_token_secret, oauth_verifier):
        request_token = {
            'oauth_token': oauth_token,
            'oauth_token_secret': oauth_token_secret,
            'oauth_callback_confirmed': True
        }
        logging.info("oauth_token:%s..." % oauth_token[:8])
        logging.info("oauth_token_secret:%s..." % oauth_token_secret[:8])
        logging.info("oauth_verifier:%s..." % oauth_verifier[:8])
        if request_token is None or oauth_verifier is None:
            raise Exception("token or verifier is none.")
        auth = tweepy.OAuthHandler(self.config.twitter['consumer_key'],
                                   self.config.twitter['consumer_secret'], self.config.twitter['callback'])
        auth.request_token = request_token
        try:
            auth.get_access_token(oauth_verifier)
            return tweepy.API(auth)
        except tweepy.TweepError as e:
            logging.error(e.reason)
            raise Exception("get_user_api_obj:%s" % e.reason)

    def get_user_data(self, screen, cashe=True):
        if len(self.get_user_cashe) > 100:
            rand_index = random.choice(list(self.get_user_cashe))
            self.get_user_cashe.pop(rand_index)

        if screen in self.get_user_cashe and cashe:
            return self.get_user_cashe[screen]
        else:
            user_data = self.twi.get_user(screen_name=screen)
            self.get_user_cashe[screen] = user_data
            return user_data

    def update_user_status(self, msg):
        now = int(time.time())
        if self.update_status_fav_mode > now:
            return None  # Fav modeによりツイートせず

        try:
            # 60分以内に100回以上つぶやいたらFavモード
            self.update_status_limit = [
                n for n in self.update_status_limit if n > now - 3600
            ] + [now]
            if len(self.update_status_limit) > 100:
                self.update_status_fav_mode = now + 3600
                self.twi.update_status(status="【Info】Fav通知モードに移行したよ！当分はつぶやかないよ！(%s)" % now)
                logging.error("Fav通知モードへ移行, by myself")
                return None
            else:
                return self.twi.update_status(status=msg).id

        except tweepy.TweepError as e:
            error_code = json.loads(e.reason.replace("'", "\""))[0]
            if error_code['code'] == 88:
                # 使いすぎにより fav mode へ
                self.update_status_fav_mode = now + 20*60
                logging.error("Fav通知モードへ移行, by twitter")
            else:
                logging.error("ツイートエラー %s" % error_code['message'])
                return None

    def put_direct_msg(self, screen, msgs):
        try:
            logging.info("POST DM:%s" % screen)
            return self.twi.send_direct_message(screen_name=screen, text=msgs)
        except tweepy.TweepError as e:
            error_code = json.loads(e.reason.replace("'", "\""))[0]
            logging.error("# send DM %s" % error_code['message'])
            raise Exception(error_code['code'])

    def put_iine(self, id):
        """ tweet idにいいねを押す """
        try:
            logging.info("POST iine: %s" % id)
            self.twi.create_favorite(id=id)
        except tweepy.TweepError as e:
            error_code = json.loads(e.reason.replace("'", "\""))[0]
            logging.error("# put iine %s" % error_code['message'])
            raise Exception(error_code['code'])

    def be_friend(self, screen):
        try:
            logging.info("POST friend:%s" % screen)
            self.twi.create_friendship(screen_name=screen, follow=False)
        except tweepy.TweepError as e:
            error_code = json.loads(e.reason.replace("'", "\""))[0]
            logging.error("# be friend %s" % error_code['message'])
            raise Exception(error_code['code'])

    def reply_to(self, recipient_id, recipient_screen, txt):
        """ reply to a tweet id """
        try:
            logging.info("POST reply to:%s, id:%s" % (recipient_screen, recipient_id))
            data = self.twi.update_status(status="@%s %s" % (recipient_screen, txt), in_reply_to_status_id=recipient_id)
            return data
        except tweepy.TweepError as e:
            error_code = json.loads(e.reason.replace("'", "\""))[0]
            logging.error("reply_error: %s" % error_code['message'])
            reply = "@%s %s" % (recipient_screen, txt)
            logging.info("reply(%swords):\n%s" % (len(reply), reply))
            return False

    def reply_continue(self, msg_list, reply_to_id=None, screen_user=None):
        start = 0
        stop = 1
        finish = len(msg_list)
        count = 0
        len_fix = 0
        screen_user = screen_user or self.screen

        while True:
            count += 1
            if count > 100 or len_fix > 100:
                raise Exception("twitter_lib: too match count up or prefix")
            test_msg = "\n".join(msg_list[start:stop])

            if finish <= stop and len(test_msg) <= 130 - len_fix:
                post_msg = "\n".join(msg_list[start:stop])
                logging.info(" ".join(msg_list[start:stop]))
                try:
                    reply_to_id = self.twi.update_status(
                        status="@%s %s" % (screen_user, post_msg),
                        in_reply_to_status_id=reply_to_id
                    ).id
                    break
                except tweepy.TweepError as e:
                    error_code = json.loads(e.reason.replace("'", "\""))[0]
                    if error_code['code'] == 186:
                        len_fix += 3
                        stop -= 1
                        continue
                    elif error_code['code'] == 187:
                        raise Exception(error_code['message'])
                    else:
                        logging.info(e)
                        len_fix += 1
                        continue
                except Exception as e:
                    logging.error(e)

            if len(test_msg) > 130 - len_fix:
                post_msg = "\n".join(msg_list[start:stop - 1])
                logging.info(" ".join(msg_list[start:stop - 1]))
                try:
                    reply_to_id = self.twi.update_status(
                        status="@%s %s" % (screen_user, post_msg),
                        in_reply_to_status_id=reply_to_id
                    ).id
                    time.sleep(1)
                    screen_user = self.screen
                    start = stop - 1
                    len_fix = 0
                    continue
                except tweepy.TweepError as e:
                    error_code = json.loads(e.reason.replace("'", "\""))[0]
                    if error_code['code'] == 186:
                        len_fix += 3
                        stop -= 1
                        continue
                    elif error_code['code'] == 187:
                        raise Exception(error_code['message'])
                    else:
                        logging.error(e)
                        len_fix += 1
                        continue
                except Exception as e:
                    logging.error(e)
            else:
                stop += 1
        return reply_to_id

    def selfcheck_twitter(self):
        r = self.twi.verify_credentials()
        if r.screen_name != self.screen:
            error = "raised error correct:%s wrong:%s\n" % (r.screen_name, self.screen)
            error += "screen name don't incrude @, please check.'@example' is wrong, 'example' is correct."
            raise Exception(error)
        else:
            logging.info("self check OK!")
            return

