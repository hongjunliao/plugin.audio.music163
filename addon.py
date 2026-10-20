# -*- coding:utf-8 -*-
from api import NetEase
from xbmcswift2 import Plugin, xbmcgui, xbmcplugin, xbmc, xbmcaddon
import re
import sys
import hashlib
import time
import os
import xbmcvfs
import qrcode
from datetime import datetime
import json
try:
    xbmc.translatePath = xbmcvfs.translatePath
except AttributeError:
    pass

PY3 = sys.version_info.major >= 3
if not PY3:
    reload(sys)
    sys.setdefaultencoding('utf-8')

plugin = Plugin()

account = plugin.get_storage('account')
if 'uid' not in account:
    account['uid'] = ''
if 'logined' not in account:
    account['logined'] = False
if 'first_run' not in account:
    account['first_run'] = True

music = NetEase()

PROFILE = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
qrcode_path = os.path.join(PROFILE, 'qrcode')


def delete_files(path):
    files = os.listdir(path)
    for f in files:
        f_path = os.path.join(path, f)
        if os.path.isdir(f_path):
            delete_files(f_path)
        else:
            os.remove(f_path)


def caculate_size(path):
    count = 0
    size = 0
    files = os.listdir(path)
    for f in files:
        f_path = os.path.join(path, f)
        if os.path.isdir(f_path):
            count_, size_ = caculate_size(f_path)
            count += count_
            size += size_
        else:
            count += 1
            size += os.path.getsize(f_path)
    return count, size


def qrcode_check():
    if not os.path.exists(qrcode_path):
        SUCCESS = xbmcvfs.mkdir(qrcode_path)
        if not SUCCESS:
            dialog = xbmcgui.Dialog()
            dialog.notification('失败', '目录创建失败，无法使用该功能', xbmcgui.NOTIFICATION_INFO, 800, False)
            return False
        else:
            temp_path = os.path.join(qrcode_path, str(int(time.time()))+'.png')
            img = qrcode.make('temp_img')
            img.save(temp_path)

    _, files = xbmcvfs.listdir(qrcode_path)
    for file in files:
        xbmcvfs.delete(os.path.join(qrcode_path, file))
    return True


def check_login_status(key, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            check_result = music.login_qr_check(key)
            code = check_result.get('code', 0)
            if code == 803:
                account['logined'] = True
                resp = music.user_level()
                account['uid'] = resp.get('data', {}).get('userId', '')
                dialog = xbmcgui.Dialog()
                dialog.notification('登录成功', '扫码登录成功，请重启软件', xbmcgui.NOTIFICATION_INFO, 800, False)
                xbmc.executebuiltin('Action(Back)')
                return True
        except Exception as e:
            print("qr poll error: %s" % e)
        time.sleep(3)
    dialog = xbmcgui.Dialog()
    dialog.notification('扫码登录', '登录超时或被拦截，请重试', xbmcgui.NOTIFICATION_INFO, 800, False)
    xbmc.executebuiltin('Action(Back)')
    return False


@plugin.route('/qrcode_login/')
def qrcode_login():
    if not qrcode_check():
        return
    result = music.login_qr_key()
    key = result.get('unikey', '')
    if not key:
        dialog = xbmcgui.Dialog()
        dialog.notification('扫码登录', '获取二维码key失败，可能被风控拦截', xbmcgui.NOTIFICATION_INFO, 800, False)
        return
    login_path = 'https://music.163.com/login?codekey={}'.format(key)

    temp_path = os.path.join(qrcode_path, str(int(time.time())) + '.png')
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=20
    )
    qr.add_data(login_path)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(temp_path)
    dialog = xbmcgui.Dialog()
    ok = dialog.yesno('扫码登录', '请用手机端扫码确认登录', '取消', '确认')
    if not ok:
        return
    xbmc.executebuiltin('ShowPicture(%s)' % temp_path)
    check_login_status(key, timeout=120)


# original addon.py continues unchanged below ...
