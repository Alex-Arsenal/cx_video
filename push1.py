# -*- coding:utf-8 -*-

import os, datetime, logging
from datetime import date, timedelta
from datetime import datetime
from jinja2 import Environment, PackageLoader, FileSystemLoader
from os import path, listdir, system
from shutil import copy
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import mimetypes
from random import randrange
import time
import sys
import pymysql

# reload(sys)
# sys.setdefaultencoding("utf-8")

# 动态载入手工处理的feeds

from elasticsearch import Elasticsearch, helpers

client = Elasticsearch(["http://127.0.0.1"], http_auth=('elastic', '008800'), port=9200)
db_name = 'test'
db_user = 'root'
db_pass = 'gjtczq38'
db_ip = '127.0.0.1'
db_port = 3306
# 第三方 SMTP 服务
mail_host = "smtp.163.com"  # 设置服务器
mail_user = "xuph01@163.com"  # 用户名
mail_pass = "OZZRZGANPNETQELI"  # 口令


# 生产模板
def render_and_write(template_name, context, output_name, output_dir, templates_env):
    """Render `template_name` with `context` and write the result in the file
    `output_dir`/`output_name`."""
    template = templates_env.get_template(template_name)
    f = open(path.join(output_dir, output_name), "w")
    f.write(template.render(**context).encode('utf-8'))
    f.close()


# 生产mobi
def mobi(input_file, exec_path, logging=None):
    """Execute the KindleGen binary to create a MOBI file."""
    try:
        logging.info("generate .mobi file start... ")
        system("%s %s" % (exec_path, input_file))
        return 'metadata.mobi'
    except Exception as e:
        logging.error("Error: %s" % e)
        return ''


# epub
def epub(r_path, t_path, e_path, logging=None):
    try:
        os.chdir(path.join(r_path, t_path, e_path))

        logging.info("generate .epub file start... ")
        system("zip -X -9 -r book1.epub.zip * -x mimetype")
        system("zip -X -0 book1.epub.zip mimetype")
        system("mv book1.epub.zip daily.epub")

        os.chdir(r_path)
        return 'daily.epub'
    except Exception as e:
        logging.error("Error: %s" % e)
        return ''


# 发邮件
def send_mail(from_addr, to_addr, attach_path, ifmobi, logging=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = 'NewsPlatform'
        msg.attach(MIMEText(''))
        ctype, encoding = mimetypes.guess_type(attach_path)
        if ctype is None or encoding is not None:
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        part = MIMEBase(maintype, subtype)
        with open(attach_path, 'rb') as fp:
            part.set_payload(fp.read())
        encoders.encode_base64(part)
        if ifmobi == 1:
            filename = "NewsPlatform.mobi"
        else:
            filename = "NewsPlatform.epub"
        part.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(part)
        try:
            smtpObj = smtplib.SMTP_SSL()
            smtpObj.connect(mail_host, 465)
            smtpObj.login(mail_user, mail_pass)
            smtpObj.sendmail(from_addr, to_addr, msg.as_string())
            smtpObj.quit()
            print("邮件发送成功")
        except smtplib.SMTPException:
            import traceback
            traceback.print_exc()
            print("Error: 无法发送邮件")
    except Exception as e:
        logging.error("fail:%s" % e)


# 从mysql中提取数据
def pushwork3(email, feeds, ifimg, ifmobi):  # feeds只存有编号,ifmobi=1
    # 相关信息
    print(email)
    log = logging.getLogger()
    sum_pic_size = 0  # getsize('test.png')/1024 MAX_PIC_SIZE
    data = []
    feed_number = 1
    play_order = 0
    # 总的img计数
    imgindex_temp = 0
    temp_sec = ''

    ROOT = path.dirname(path.abspath(__file__))
    if ifmobi == 1:
        output_dir = path.join(ROOT, 'temp', 'mobi')
    else:
        output_dir = path.join(ROOT, 'temp', 'epub', 'OEBPS')

    templates_env = Environment(loader=PackageLoader('bmaintest', 'templates20200624'))

    img_num = []

    i = 0  # 对feed进行计数
    yesterday = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    websites = {'New York Times': 'nytimes', 'Bloomberg': 'bloomberg', 'Bloomberg_Week': 'bloomberg_week',
                'Bloomberg_Daily': 'bloomberg_daily', 'nytimestoday_daily': 'nytimestoday_daily'}
    websites1 = {'nytimes': 'NYT', 'bloomberg': 'BBG', 'bloomberg_week': 'BBG_Week',
                 'bloomberg_daily': 'BBG_Daily', 'nytimestoday_daily': 'NYT_Daily'}
    for feed in feeds:
        website = websites[feed]
        tag = feeds[feed]
        body = {
            "track_total_hits": "true",
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "daily_or_week": website,

                            }
                        },
                        {
                            "terms": {
                                "inssue_tag": tag

                            }
                        },
                        {
                            "range": {
                                "datepublished": {
                                    "gte": yesterday,  # datetime.now().strftime('%Y-%m-%d'),
                                    "format": "yyyy-MM-dd HH:mm:ss"
                                }
                            }
                        }
                    ],
                }
            },
            "sort": [
                {
                    "datepublished": {
                        "order": "desc"
                    }
                }
            ],
            "from": 0,
            "size": 1000,
        }
        article_all = client.search(index="news2020s", body=body)
        total_nums = article_all["hits"]["total"]["value"]
        if total_nums > 0:
            for article in article_all["hits"]["hits"]:
                i += 1
                contents = []
                for content in article["_source"]['contents']:
                    temp = {}
                    if content.startswith("https://"):
                        temp['image'] = content
                        if os.path.exists(
                                "/lenovoprogram/spider/image/" + content.lstrip("https:/trends.lenovoresearch.cn/")):
                            copy("/lenovoprogram/spider/image/" + content.lstrip("https:/trends.lenovoresearch.cn/"),
                                 "/home/RedKindle/temp/mobi/https:/trends.lenovoresearch.cn/")

                    else:
                        temp['content'] = content
                    contents.append(temp)
                author_list = ""
                if "authors" in article["_source"]:
                    for auth in article["_source"]['authors']:
                        author_list += auth + ";  "
                        author_list = author_list.rstrip(";  ")
                else:
                    author_list = ""
                if len(data) == 0:
                    local_entry = {
                        'play_order': 1,
                        'title': article["_source"]['title'],
                        'content': contents,
                        'web_source': article["_source"]['website'],
                        'tag': article["_source"]['inssue_tag'],
                        'date': article["_source"]['datepublished'].split("T")[0],
                        'contents': contents,
                        'author_list': author_list,
                        'url': "https://trends.lenovoresearch.cn/test/article/article-detail/?article_id=" +
                               article["_source"]['url_encryption'],
                    }
                    temp = {'web_source': websites1[article["_source"]['daily_or_week']] + '-' + article["_source"][
                        'inssue_tag'],
                            'content': [local_entry], 'number': feed_number}
                    data.append(temp)
                    feed_number += 1
                else:
                    flag = False
                    for t in range(len(data)):
                        if websites1[article["_source"]['daily_or_week']] + '-' + article["_source"]['inssue_tag'] == \
                                data[t]['web_source']:
                            local_entry = {
                                'play_order': len(data[t]['content']) + 1,
                                'title': article["_source"]['title'],
                                'content': contents,
                                'web_source': article["_source"]['website'],
                                'tag': article["_source"]['inssue_tag'],
                                'date': article["_source"]['datepublished'].split("T")[0],
                                'contents': contents,
                                'author_list': author_list,
                                'url': "https://trends.lenovoresearch.cn/test/article/article-detail/?article_id=" +
                                       article["_source"]['url_encryption'],
                            }
                            data[t]['content'].append(local_entry)
                            flag = True
                    if flag == False:
                        local_entry = {
                            'play_order': 1,
                            'title': article["_source"]['title'],
                            'content': contents,
                            'web_source': article["_source"]['website'],
                            'tag': article["_source"]['inssue_tag'],
                            'date': article["_source"]['datepublished'].split("T")[0],
                            'contents': contents,
                            'author_list': author_list,
                            'url': "https://trends.lenovoresearch.cn/test/article/article-detail/?article_id=" +
                                   article["_source"]['url_encryption'],
                        }
                        temp = {'web_source': websites1[article["_source"]['daily_or_week']] + '-' + article["_source"][
                            'inssue_tag'],
                                'content': [local_entry], 'number': feed_number}
                        data.append(temp)
                        feed_number += 1
        # 图片
        if ifimg == 1:
            img_dir = path.join(ROOT, 'temp', 'feed_%s' % feed)
            for fn in listdir(img_dir):
                if sum_pic_size < 10 * 1024:
                    f_path = path.join(img_dir, fn)
                    sum_pic_size += path.getsize(f_path) / 1024
                    img_num.append(fn)
                    copy(f_path, path.join(output_dir, fn))
                    imgindex_temp += 1
        else:
            imgindex_temp = 0
            img_num = []

    # ==============================end for
    wrap = {
        'date': date.today().isoformat(),
        'feeds': data,
        'img_nums': imgindex_temp,
        'img_name': img_num,
    }
    # TOC (NCX)
    render_and_write('toc.xml', wrap, 'toc.ncx', output_dir, templates_env)
    # COVER (HTML)
    render_and_write('cover.html', wrap, 'cover.html', output_dir, templates_env)
    # TOC (HTML)
    render_and_write('toc.html', wrap, 'toc.html', output_dir, templates_env)
    # OPF
    render_and_write('opf.xml', wrap, 'metadata.opf', output_dir, templates_env)
    # /home/zzh/Desktop/temp/v3
    for feed in data:
        for cont in feed['content']:
            render_and_write('feed.html', cont, 'article_%s_%s.html' % (feed['number'], cont['play_order']), output_dir,
                             templates_env)

    # copy cover.jpg
    copy(path.join(ROOT, 'templates20200624', 'masthead.gif'), path.join(output_dir, 'masthead.gif'))
    copy(path.join(ROOT, 'templates20200624', 'cover.jpg'), path.join(output_dir, 'cover.jpg'))

    # gen mobi
    if ifmobi == 1:
        mobi_file = mobi(path.join(output_dir, 'metadata.opf'), path.join(ROOT, 'kindlegen_1.1'), log)

        if mobi_file:
            mobi_file = path.join(output_dir, mobi_file)
            send_mail("xuph01@163.com", email, mobi_file, 1, log)
    else:
        epub_file = epub(ROOT, 'temp', 'epub', log)

        if epub_file:
            epub_file = path.join(ROOT, 'temp', 'epub', epub_file)
            send_mail("xuph01@163.com", email, epub_file, 0, log)
            if path.isfile(epub_file):
                os.remove(epub_file)

    # clean
    # for fn in listdir(output_dir):
    # 	f_path = path.join(output_dir, fn)
    # 	if path.isfile( f_path):
    # 		os.remove(f_path)
    path1 = "/home/RedKindle/temp/mobi/https:/trends.lenovoresearch.cn/"
    path2 = "/home/RedKindle/temp/"
    for root, dirs, files in os.walk(path1):
        for name in files:
            if name.endswith(".png") or name.endswith(".jpg"):
                os.remove(os.path.join(root, name))
    for root, dirs, files in os.walk(path2):
        for name in files:
            if name.endswith(".html"):
                os.remove(os.path.join(root, name))
    return '-=end=-'


if __name__ == "__main__":
    conn = pymysql.connect(db=db_name, user=db_user, passwd=db_pass, host=db_ip, port=int(db_port), charset="utf8")
    cursor = conn.cursor()
    sql = """select a.kindle_email, b.website, b.tag from user_user as a, user_subscription as b where a.id = b.user_id;"""
    cursor.execute(sql)
    results = cursor.fetchall()
    users_all = {}
    for i in results:
        if i[0] in users_all:
            if i[1] in users_all[i[0]]:
                users_all[i[0]][i[1]].append(i[2])
            else:
                users_all[i[0]][i[1]] = [i[2]]
        else:
            users_all[i[0]] = {i[1]: [i[2]]}
    for i in users_all:
        if i.endswith('@kindle.cn') or i.endswith('@163.com') or i.endswith('@outlook.com') or i.endswith(
                '@lenovo.com') or i.endswith('@qq.com'):
            pushwork3('xuph01@163.com', users_all[i], 0, 1)
            break
