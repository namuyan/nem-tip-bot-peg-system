#!/user/env python3
# -*- coding: utf-8 -*-


from binascii import hexlify


def bytes2hex(b, num=32):
    h = hexlify(b)
    return "0x" + (num * 2 - len(h)) * "0" + h.decode()
