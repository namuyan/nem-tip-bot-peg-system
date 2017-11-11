#!/user/env python3
# -*- coding: utf-8 -*-


from config import Config, EmptyObject, MICRO_TO_WEI, NUKO_TO_WEI
from init import Init
from ether_interface import EtherInterface
from tipnem_control import TipnemControl
from incoming import IncomingPolling
from rest_api import RestApi
import time
import logging
import sys

version = "1.0"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(levelname)-6s] [%(threadName)-10s] [%(asctime)-24s] %(message)s')
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
sh.setFormatter(formatter)
logger.addHandler(sh)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


def main(mycfg):
    logging.info("# start system")

    init = Init(mycfg=mycfg)
    init.check()
    init.close()
    logging.info("# finish initialize")

    """ Class """
    obj = EmptyObject()
    obj.neko = EtherInterface(mycfg=mycfg)
    obj.tip = TipnemControl(mycfg=mycfg)
    obj.income = IncomingPolling(mycfg=mycfg)
    obj.rest = RestApi(mycfg=mycfg)

    """ import object """
    obj.neko.obj = obj
    obj.tip.obj = obj
    obj.income.obj = obj
    obj.rest.obj = obj

    """ threading start """
    obj.income.start()
    obj.rest.start()
    obj.tip.start_control()  # blocking main thread

    """ check """
    count = 0
    while True:
        try:
            count += 1
            time.sleep(1)
            if mycfg.stop_signal:
                raise Exception("kill signal")
            if count % 1800 == 0:
                logging.info("# checking living %d" % count)

        except Exception as e:
            logging.info("# input stop signal")
            while True:
                mycfg.stop_signal = True
                time.sleep(1)
                for name in mycfg.stop_need_obj:
                    if name not in mycfg.stop_ok:
                        logging.info("# wait for %s" % name)
                        break
                else:
                    logging.info("# exit ok!")
                    exit(0)

if __name__ == '__main__':
    if 'main' in sys.argv:
        test = False
    else:
        test = True
        logging.info("# test mode!")
    config = Config(test=test)
    main(mycfg=config)
