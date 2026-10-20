# -*- coding:utf-8 -*-
import json
import os
import sys
import time
import requests
from encrypt import encrypted_request
from xbmcswift2 import xbmc, xbmcaddon, xbmcplugin
from http.cookiejar import Cookie
from http.cookiejar import MozillaCookieJar
import xbmcvfs

DEFAULT_TIMEOUT = 10
BASE_URL = "https://music.163.com"

PROFILE = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
if not os.path.exists(PROFILE):
    os.makedirs(PROFILE)
COOKIE_PATH = os.path.join(PROFILE, 'cookie.txt')
if not os.path.exists(COOKIE_PATH):
    with open(COOKIE_PATH, 'w') as f:
        f.write('# Netscape HTTP Cookie File\n')


class NetEase(object):
    def __init__(self):
        self.header = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://music.163.com",
            "Referer": "https://music.163.com/",
            "Host": "music.163.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        cookie_jar = MozillaCookieJar(COOKIE_PATH)
        try:
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
        self.session = requests.Session()
        self.session.cookies = cookie_jar
        self.session.headers.update(self.header)
        self.enable_proxy = False
        self.proxies = {}
        if xbmcplugin.getSetting(int(sys.argv[1]), 'enable_proxy') == 'true':
            self.enable_proxy = True
            proxy = xbmcplugin.getSetting(int(sys.argv[1]), 'host').strip()
            port = xbmcplugin.getSetting(int(sys.argv[1]), 'port').strip()
            self.proxies = {
                'http': 'http://' + proxy + ':' + port,
                'https': 'https://' + proxy + ':' + port,
            }

    def _raw_request(self, method, endpoint, data=None):
        if method == "GET":
            if not self.enable_proxy:
                return self.session.get(endpoint, params=data, timeout=DEFAULT_TIMEOUT)
            return self.session.get(endpoint, params=data, timeout=DEFAULT_TIMEOUT, proxies=self.proxies, verify=False)
        elif method == "POST":
            if not self.enable_proxy:
                return self.session.post(endpoint, data=data, timeout=DEFAULT_TIMEOUT)
            return self.session.post(endpoint, data=data, timeout=DEFAULT_TIMEOUT, proxies=self.proxies, verify=False)
        raise ValueError("Unsupported method: %s" % method)

    def request(self, method, path, params={}, default={"code": -1}, custom_cookies={}):
        endpoint = "{}{}".format(BASE_URL, path)
        csrf_token = ""
        for cookie in self.session.cookies:
            if cookie.name == "__csrf":
                csrf_token = cookie.value
                break
        params = dict(params)
        params.update({"csrf_token": csrf_token})
        data = default

        for key, value in custom_cookies.items():
            cookie = self.make_cookie(key, value)
            self.session.cookies.set_cookie(cookie)

        payload = encrypted_request(params)
        try:
            resp = self._raw_request(method, endpoint, payload)
            if resp is None:
                return {"code": -1, "msg": "null response"}
            if resp.status_code == 403:
                return {"code": -403, "msg": "403 forbidden"}
            data = resp.json()
            if not isinstance(data, dict):
                return {"code": -1, "msg": "invalid json"}
            if 'code' not in data:
                data['code'] = resp.status_code
        except requests.exceptions.RequestException as e:
            print(e)
            return {"code": -1, "msg": str(e)}
        except ValueError as e:
            print("Path: {}, response: {}".format(path, resp.text[:200]))
            return {"code": -1, "msg": "invalid json"}
        return data

    def make_cookie(self, name, value):
        return Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain="music.163.com",
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
        )

    def login(self, username, password):
        if username.isdigit():
            path = "/weapi/login/cellphone"
            params = dict(phone=username, password=password, rememberLogin="true")
        else:
            client_token = "1_jVUMqWEPke0/1/Vu56xCmJpo5vP1grjn_SOVVDzOc78w8OKLVZ2JH7IfkjSXqgfmh"
            path = "/weapi/login"
            params = dict(username=username, password=password, rememberLogin="true", clientToken=client_token)
        data = self.request("POST", path, params)
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return data

    def login_qr_key(self):
        path = "/weapi/login/qrcode/unikey"
        params = dict(type=1)
        result = self.request("POST", path, params)
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return result

    def login_qr_check(self, key):
        path = "/weapi/login/qrcode/client/login"
        params = dict(key=key, type=1)
        data = self.request("POST", path, params)
        if data.get('code', 0) in [801, 802, 803]:
            self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return data

    def daily_task(self, is_mobile=True):
        path = "/weapi/point/dailyTask"
        params = dict(type=0 if is_mobile else 1)
        return self.request("POST", path, params)

    def user_playlist(self, uid, offset=0, limit=1000, includeVideo=True):
        path = "/weapi/user/playlist"
        params = dict(uid=uid, offset=offset, limit=limit, includeVideo=includeVideo, csrf_token="")
        return self.request("POST", path, params)

    def user_level(self):
        path = "/weapi/user/level"
        return self.request("POST", path)

    def vip_timemachine(self, startTime, endTime, limit=60):
        path = '/weapi/vipmusic/newrecord/weekflow'
        params = dict(startTime=startTime, endTime=endTime, type=1, limit=limit)
        return self.request("POST", path, params)

    def songs_detail(self, ids):
        path = "/weapi/v3/song/detail"
        params = dict(c=json.dumps([{"id": _id} for _id in ids]), ids=json.dumps(ids))
        return self.request("POST", path, params)

    def songs_url_v1(self, ids, level):
        path = "/weapi/song/enhance/player/url/v1"
        if level == 'dolby':
            params = dict(ids=ids, level='hires', effects='["dolby"]', encodeType='mp4')
            return self.request("POST", path, params, custom_cookies={'os': 'pc', 'appver': '2.10.11.201538'})
        else:
            params = dict(ids=ids, level=level, encodeType='flac')
            return self.request("POST", path, params)

    def mv_url(self, id, r=1080):
        path = "/weapi/song/enhance/play/mv/url"
        params = dict(id=id, r=r)
        return self.request("POST", path, params)

    def mlog_detail(self, id, resolution=720, type=1):
        path = "/weapi/mlog/detail/v1"
        params = dict(id=id, resolution=resolution, type=type)
        return self.request("POST", path, params)

    def playlist_detail(self, id, shareUserId=0):
        path = "/weapi/v6/playlist/detail"
        params = dict(id=id, t=int(time.time()), n=1000, s=5, shareUserId=shareUserId)
        return self.request("POST", path, params)

    def playlist_create(self, name, privacy=0, ptype='NORMAL'):
        path = "/weapi/playlist/create"
        params = dict(name=name, privacy=privacy, type=ptype)
        return self.request("POST", path, params)

    def playlist_tracks(self, pid, ids, op='add'):
        path = "/weapi/playlist/manipulate/tracks"
        params = {'op': op, 'pid': pid, 'trackIds': json.dumps(ids), 'imme': 'true'}
        result = self.request("POST", path, params)
        if result.get('code') != 200:
            ids.extend(ids)
            params = {'op': op, 'pid': pid, 'trackIds': json.dumps(ids), 'imme': 'true'}
            result = self.request("POST", path, params)
        return result

    def playlist_subscribe(self, id):
        path = "/weapi/playlist/subscribe"
        params = dict(id=id)
        return self.request("POST", path, params)

    def playlist_unsubscribe(self, id):
        path = "/weapi/playlist/unsubscribe"
        params = dict(id=id)
        return self.request("POST", path, params)

    def playlist_delete(self, ids):
        path = "/weapi/playlist/remove"
        params = dict(ids=ids)
        return self.request("POST", path, params)

    def search(self, keywords, stype=1, offset=0, total="true", limit=100):
        path = "/weapi/search/get"
        params = dict(s=keywords, type=stype, offset=offset, total=total, limit=limit)
        return self.request("POST", path, params)

    def cloud_songlist(self, offset=0, limit=50):
        path = "/weapi/v1/cloud/get"
        params = dict(offset=offset, limit=limit, csrf_token="")
        return self.request("POST", path, params)

    def user_detail(self, id):
        path = "/weapi/v1/user/detail/{}".format(id)
        return self.request("POST", path)

    def user_follow(self, id):
        path = "/weapi/user/follow/{}".format(id)
        return self.request("POST", path)

    def user_delfollow(self, id):
        path = "/weapi/user/delfollow/{}".format(id)
        return self.request("POST", path)

    def user_getfollows(self, id, offset=0, limit=50, order=True):
        path = "/weapi/user/getfollows/{}".format(id)
        params = dict(offset=offset, limit=limit, order=order)
        return self.request("POST", path, params)

    def user_getfolloweds(self, userId, offset=0, limit=30):
        path = "/weapi/user/getfolloweds"
        params = dict(userId=userId, offset=offset, limit=limit, getcounts=True)
        return self.request("POST", path, params)

    def play_record(self, uid, type=0):
        path = "/weapi/v1/play/record"
        params = dict(uid=uid, type=type)
        return self.request("POST", path, params)

    def personal_fm(self):
        path = "/weapi/v1/radio/get"
        return self.request("POST", path)

    def recommend_playlist(self, total=True, offset=0, limit=20):
        path = "/weapi/v3/discovery/recommend/songs"
        params = dict(total=total, offset=offset, limit=limit, csrf_token="")
        return self.request("POST", path, params)

    def history_recommend_recent(self):
        path = "/weapi/discovery/recommend/songs/history/recent"
        return self.request("POST", path)

    def history_recommend_detail(self, date=''):
        path = "/weapi/discovery/recommend/songs/history/detail"
        params = dict(date=date)
        return self.request("POST", path, params)

    def recommend_resource(self):
        path = "/weapi/v1/discovery/recommend/resource"
        return self.request("POST", path)

    def top_mv(self, area='', limit=50, offset=0, total=True):
        path = "/weapi/mv/toplist"
        params = dict(area=area, limit=limit, offset=offset, total=total)
        return self.request("POST", path, params)

    def toplists(self):
        path = "/api/toplist"
        return self.request("POST", path)

    def dj_sublist(self, offset=0, limit=50):
        path = "/weapi/djradio/get/subed"
        params = dict(offset=offset, limit=limit, total=True)
        return self.request("POST", path, params)

    def dj_program(self, radio_id, asc=False, offset=0, limit=50):
        path = "/weapi/dj/program/byradio"
        params = dict(asc=asc, radioId=radio_id, offset=offset, limit=limit)
        return self.request("POST", path, params)

    def dj_detail(self, id):
        path = "/weapi/dj/program/detail"
        params = dict(id=id)
        return self.request("POST", path, params)

    def artist_top(self, offset=0, limit=100, total=True):
        path = "/weapi/artist/top"
        params = dict(offset=offset, total=total, limit=limit)
        return self.request("POST", path, params)

    def artists(self, artist_id):
        path = "/weapi/v1/artist/{}".format(artist_id)
        return self.request("POST", path)

    def artist_album(self, artist_id, offset=0, limit=50):
        path = "/weapi/artist/albums/{}".format(artist_id)
        params = dict(offset=offset, total=True, limit=limit)
        return self.request("POST", path, params)

    def artist_songs(self, id, limit=50, offset=0):
        path = "/weapi/v1/artist/songs"
        params = dict(id=id, limit=limit, offset=offset, private_cloud=True, work_type=1, order='hot')
        return self.request("POST", path, params)

    def album(self, album_id):
        path = "/weapi/v1/album/{}".format(album_id)
        return self.request("POST", path)

    def artist_info(self, artist_id):
        path = "/weapi/v1/artist/{}".format(artist_id)
        return self.request("POST", path)

    def artist_mvs(self, id, offset=0, limit=50, total=True):
        path = "/weapi/artist/mvs"
        params = dict(artistId=id, offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def similar_artist(self, artistid):
        path = "/weapi/discovery/simiArtist"
        params = dict(artistid=artistid)
        return self.request("POST", path, params)

    def video_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/cloudvideo/allvideo/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def video_url(self, id, resolution=1080):
        path = "/weapi/cloudvideo/playurl"
        params = dict(ids='["' + id + '"]', resolution=resolution)
        return self.request("POST", path, params)

    def digitalAlbum_purchased(self, offset=0, limit=50, total=True):
        path = "/api/digitalAlbum/purchased"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def single_purchased(self, offset=0, limit=1000, total=True):
        path = "/weapi/single/mybought/song/list"
        params = dict(offset=offset, limit=limit)
        return self.request("POST", path, params)

    def artist_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/artist/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def album_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/album/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def top_artists(self, offset=0, limit=100, total=True):
        path = "/weapi/artist/top"
        params = dict(offset=offset, total=total, limit=limit)
        return self.request("POST", path, params)

    def new_songs(self, areaId=0, total=True):
        path = "/weapi/v1/discovery/new/songs"
        params = dict(areaId=areaId, total=total)
        return self.request("POST", path, params)

    def new_albums(self, offset=0, limit=50):
        path = "/weapi/album/new"
        params = dict(area="ALL", offset=offset, total=True, limit=limit)
        return self.request("POST", path, params)

    def song_lyric(self, music_id):
        path = "/weapi/song/lyric"
        params = dict(os="osx", id=music_id, lv=-1, kv=-1, tv=-1)
        return self.request("POST", path, params)

    def daka(self, id, sourceId=0, time=240):
        path = "/weapi/feedback/weblog"
        params = {'logs': json.dumps([{'action': 'play', 'json': {"download": 0, "end": 'playend', "id": id, "sourceId": sourceId, "time": time, "type": 'song', "wifi": 0}}])}
        return self.request("POST", path, params)

    def playlist_add(self, pid, ids):
        path = "/weapi/playlist/track/add"
        ids = [{'type': 3, 'id': song_id} for song_id in ids]
        params = {'id': pid, 'tracks': json.dumps(ids)}
        return self.request("POST", path, params)

    def history_recommend_dates(self):
        return self.history_recommend_recent().get('data', {}).get('dates', [])

    def mlog_socialsquare(self, channelId=1001, pagenum=0):
        path = "/weapi/socialsquare/v1/get"
        params = dict(pagenum=pagenum, netstate=1, first=(str(pagenum) == '0'), channelId=channelId, dailyHot=(str(pagenum) == '0'))
        return self.request("POST", path, params)

    def mlog_rcmd(self, id, limit=3, type=1, rcmdType=0, lastRcmdResType=1, lastRcmdResId='', viewCount=1, channelId=1001):
        path = "/weapi/mlog/rcmd/v3"
        params = dict(id=id, limit=limit, type=type, rcmdType=rcmdType, lastRcmdResType=lastRcmdResType, extInfo=dict(channelId=channelId), viewCount=viewCount)
        return self.request("POST", path, params)

    def user_getfolloweds(self, userId, offset=0, limit=30):
        path = "/weapi/user/getfolloweds"
        params = dict(userId=userId, offset=offset, limit=limit, getcounts=True)
        return self.request("POST", path, params)

    def user_getfollows(self, id, offset=0, limit=50, order=True):
        path = "/weapi/user/getfollows/{}".format(id)
        params = dict(offset=offset, limit=limit, order=order)
        return self.request("POST", path, params)

    def artist_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/artist/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def album_sublist(self, offset=0, limit=50, total=True):
        path = "/weapi/album/sublist"
        params = dict(offset=offset, limit=limit, total=total)
        return self.request("POST", path, params)

    def toplists(self):
        path = "/api/toplist"
        return self.request("POST", path)

    def new_albums(self, offset=0, limit=50):
        path = "/weapi/album/new"
        params = dict(area="ALL", offset=offset, total=True, limit=limit)
        return self.request("POST", path, params)

    def login_qr_key(self):
        path = "/weapi/login/qrcode/unikey"
        params = dict(type=1)
        return self.request("POST", path, params)

    def login_qr_check(self, key):
        path = "/weapi/login/qrcode/client/login"
        params = dict(key=key, type=1)
        return self.request("POST", path, params)

    def user_level(self):
        path = "/weapi/user/level"
        return self.request("POST", path)


# Add the QR login status machine in addon.py

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
        border=20,
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


# End of patch
