# -*- coding: utf-8 -*-

# 打卡脚修改自ZJU-nCov-Hitcarder的开源代码，感谢这位同学开源的代码

import requests
import json
import re
import datetime
import time
import sys
# import ddddocr


 
from dingtalkchatbot.chatbot import DingtalkChatbot




class ClockIn(object):
    """Hit card class
    Attributes:
        eai_sess: (str) cookie of healthreport.zju.edu.cn/ncov/wap/default/index
        LOGIN_URL: (str) 登录url
        BASE_URL: (str) 打卡首页url
        SAVE_URL: (str) 提交打卡url
        HEADERS: (dir) 请求头
        sess: (requests.Session) 统一的session
    """
    LOGIN_URL = "https://zjuam.zju.edu.cn/cas/login?service=https%3A%2F%2Fhealthreport.zju.edu.cn%2Fa_zju%2Fapi%2Fsso%2Findex%3Fredirect%3Dhttps%253A%252F%252Fhealthreport.zju.edu.cn%252Fncov%252Fwap%252Fdefault%252Findex"
    BASE_URL = "https://healthreport.zju.edu.cn/ncov/wap/default/index"
    SAVE_URL = "https://healthreport.zju.edu.cn/ncov/wap/default/save"
    CAPTCHA_URL = 'https://healthreport.zju.edu.cn/ncov/wap/default/code'
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
    }

    def __init__(self, key, url, eai_sess = ""):
        self.key = key
        self.url = url
        self.eai_sess = eai_sess
        self.name = ""
        self.sess = requests.Session()
        # self.ocr = ddddocr.DdddOcr()

    def add_eai_sess(self, eai_sess):
        self.eai_sess = eai_sess
        cookie_dict = {'eai-sess': self.eai_sess}
        self.sess.cookies = requests.cookies.cookiejar_from_dict(cookie_dict)


    def login(self):
        """Login to ZJU platform"""
        res = self.sess.get(self.LOGIN_URL, headers=self.HEADERS)
        execution = re.search(
            'name="execution" value="(.*?)"', res.text).group(1)
        res = self.sess.get(
            url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=self.HEADERS).json()
        n, e = res['modulus'], res['exponent']
        encrypt_password = self._rsa_encrypt(self.password, e, n)

        data = {
            'username': self.username,
            'password': encrypt_password,
            'execution': execution,
            '_eventId': 'submit'
        }
        res = self.sess.post(url=self.LOGIN_URL,
                             data=data, headers=self.HEADERS)

        # check if login successfully
        if '统一身份认证' in res.content.decode():
            raise LoginError('登录失败，请核实账号密码重新登录')
        return self.sess

    def post(self):
        """Post the hitcard info"""
        res = self.sess.post(self.SAVE_URL, data=self.info,
                             headers=self.HEADERS)
        return json.loads(res.text)

    def get_date(self):
        """Get current date"""
        today = datetime.date.today()
        return "%4d%02d%02d" % (today.year, today.month, today.day)

    def get_captcha(self):
        """Get CAPTCHA code"""
        resp = self.sess.get(self.CAPTCHA_URL)
        captcha = self.ocr.classification(resp.content)
        print("验证码：", captcha)
        return captcha

    def get_info(self, html=None):
        """Get hitcard info, which is the old info with updated new time."""
        if not html:
            res = self.sess.get(self.BASE_URL, headers=self.HEADERS)
            html = res.content.decode()

        try:
            old_infos = re.findall(r'oldInfo: ({[^\n]+})', html)
            name = re.findall(r'realname: "([^\"]+)",', html)[0]
            self.name = name
            
            
            if len(old_infos) != 0:
                old_info = json.loads(old_infos[0])
            else:
                return 0
                # raise RegexMatchError("未发现缓存信息，请先至少手动成功打卡一次再运行脚本")

            new_info_tmp = json.loads(re.findall(r'def = ({[^\n]+})', html)[0])
            new_id = new_info_tmp['id']
            number = re.findall(r"number: '([^\']+)',", html)[0]
            

        except IndexError:
            raise RegexMatchError('Relative info not found in html with regex')
        except json.decoder.JSONDecodeError:
            raise DecodeError('JSON decode error')
        

        new_info = old_info.copy()
        new_info['id'] = new_id
        new_info['name'] = name
        new_info['number'] = number
        new_info["date"] = self.get_date()
        new_info["created"] = round(time.time())
        new_info["address"] = "浙江省杭州市西湖区"
        new_info["area"] = "浙江省 杭州市 西湖区"
        new_info["province"] = new_info["area"].split(' ')[0]
        new_info["city"] = new_info["area"].split(' ')[1]
        # form change
        new_info['jrdqtlqk[]'] = 0
        new_info['jrdqjcqk[]'] = 0
        new_info['sfsqhzjkk'] = 1   # 是否申领杭州健康码
        new_info['sqhzjkkys'] = 1   # 杭州健康吗颜色，1:绿色 2:红色 3:黄色
        new_info['sfqrxxss'] = 1    # 是否确认信息属实
        new_info['jcqzrq'] = ""
        new_info['gwszdd'] = ""
        new_info['szgjcs'] = ""
        # new_info['verifyCode'] = self.get_captcha()

        # 2021.08.05 Fix 2
        magics = re.findall(r'"([0-9a-f]{32})":\s*"([^\"]+)"', html)
        for item in magics:
            new_info[item[0]] = item[1]

        self.info = new_info
        return new_info

    def _rsa_encrypt(self, password_str, e_str, M_str):
        password_bytes = bytes(password_str, 'ascii')
        password_int = int.from_bytes(password_bytes, 'big')
        e_int = int(e_str, 16)
        M_int = int(M_str, 16)
        result_int = pow(password_int, e_int, M_int)
        return hex(result_int)[2:].rjust(128, '0')
    
    def sendDing(self, msg):
        webhook = self.url
        secret = self.key

        robot = DingtalkChatbot(webhook,secret=secret,pc_slide=True,fail_notice=True)
        robot.send_text(msg=msg,is_at_all=False)


# Exceptions
class LoginError(Exception):
    """Login Exception"""
    pass


class RegexMatchError(Exception):
    """Regex Matching Exception"""
    pass


class DecodeError(Exception):
    """JSON Decode Exception"""
    pass


def main(eai_sess):
    """Hit card process
    Arguments:
        eai-sess: (str) cookie of healthreport.zju.edu.cn/ncov/wap/default/index
    """
    print("\n[Time] %s" %
          datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚌 打卡任务启动")

    dk.add_eai_sess(eai_sess)

    print('正在获取个人信息...')
    try:
        if dk.get_info() != 0:
            print('已成功获取个人信息')
        else:
            return dk.name + "请手动打卡一次。"
    except Exception as err:
        print('获取信息失败，请手动打卡，更多信息: ' + str(err))
        raise Exception

    print('正在为您打卡')
    try:
        res = dk.post()
        if str(res['e']) == '0':
            print(dk.name, '已为您打卡成功！')
            return dk.name + "打卡成功！"
            #dk.sendDing(dk.name + "打卡成功！")
        else:
            print(dk.name, res['m'])
            if res['m'].find("已经") != -1:  # 已经填报过了 不报错
                # dk.sendDing(dk.name+'今日您已打卡！')
                return dk.name+'已打卡！'
            elif res['m'].find("验证码错误") != -1:  # 验证码错误
                print('再次尝试')
                time.sleep(5)
                return main(eai_sess)
            else:
                raise Exception
    except Exception:
        print('数据提交失败')
        raise Exception


if __name__ == "__main__":
    key = sys.argv[1]
    url = sys.argv[2]
    eai_sess = sys.argv[3:]
    msg_list = []
    dk = ClockIn(key, url)

    try:
        for i in eai_sess:
            try:
                msg = main(i)
            except:
                print("err")
            if msg != None:
                msg_list.append(msg)
                msg_list.append(i)
        msg_list = [(datetime.datetime.now() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')] + msg_list
        print("\n".join(msg_list))
        dk.sendDing("\n".join(msg_list))
    except Exception:
        exit(1)
    

