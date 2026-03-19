import csv
import io
import json
import os
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('PORT', '3000'))
COUNSELOR_EMAIL = os.environ.get('COUNSELOR_EMAIL', 'wenxi_deng@qq.com')
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('RATE_LIMIT_WINDOW_SECONDS', str(30 * 60)))
RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', '3'))
MIN_COMPLETION_SECONDS = int(os.environ.get('MIN_COMPLETION_SECONDS', '20'))
MAX_PAYLOAD_BYTES = int(os.environ.get('MAX_PAYLOAD_BYTES', str(200 * 1024)))
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'false').lower() == 'true'
MOCK_EMAIL = os.environ.get('MOCK_EMAIL', '0') == '1'

RATE_LIMIT_STORE = {}

QUESTIONS = ["头痛", "神经过敏，心中不踏实", "头脑中有不必要的想法或字句盘旋", "头晕和昏倒", "对异性的兴趣减退", "对旁人责备求全", "感到别人能控制您的思想", "责怪别人制造麻烦", "忘记性大", "担心自己的衣饰整齐及仪态的端正", "容易烦恼和激动", "胸痛", "害怕空旷的场所或街道", "感到自己的精力下降，活动减慢", "想结束自己的生命", "听到旁人听不到的声音", "发抖", "感到大多数人都不可信任", "胃口不好", "容易哭泣", "同异性相处时感到害羞不自在", "感到受骗、中了圈套或有人想抓住您", "无缘无故地突然感到害怕", "自己不能控制地发脾气", "怕单独出门", "经常责怪自己", "腰痛", "感到难以完成任务", "感到孤独", "感到苦闷", "过分担忧", "对事物不感兴趣", "感到害怕", "我的感情容易受到伤害", "旁人能知道您的私下想法", "感到别人不理解您不同情您", "感到人们对您不友好，不喜欢您", "做事必须做得很慢以保证做得正确", "心跳得很厉害", "恶心或胃部不舒服", "感到比不上他人", "肌肉酸痛", "感到有人在监视您谈论您", "难以入睡", "做事必须反复检查", "难以作出决定", "怕乘电车、公共汽车、地铁或火车", "呼吸有困难", "一阵阵发冷或发热", "因为感到害怕而避开某些东西、场合或活动", "脑子变空了", "身体发麻或刺痛", "喉咙有梗塞感", "感到没有前途没有希望", "不能集中注意", "感到身体的某一部分软弱无力", "感到紧张或容易紧张", "感到手或脚发重", "想到死亡的事", "吃得太多", "当别人看着您或谈论您时感到不自在", "有一些不属于您自己的想法", "有想打人或伤害他人的冲动", "醒得太早", "必须反复洗手、点数目或触摸某些东西", "睡得不稳不深", "有想摔坏或破坏东西的冲动", "有一些别人没有的想法或念头", "感到对别人神经过敏", "在商店或电影院等人多的地方感到不自在", "感到任何事情都很困难", "一阵阵恐惧或惊恐", "感到在公共场合吃东西很不舒服", "经常与人争论", "单独一人时神经很紧张", "别人对您的成绩没有作出恰当的评价", "即使和别人在一起也感到孤单", "感到坐立不安心神不定", "感到自己没有什么价值", "感到熟悉的东西变成陌生或不像是真的", "大叫或摔东西", "害怕会在公共场合昏倒", "感到别人想占您的便宜", "为一些有关“性”的想法而很苦恼", "您认为应该因为自己的过错而受到惩罚", "感到要赶快把事情做完", "感到自己的身体有严重问题", "从未感到和其他人很亲近", "感到自己有罪", "感到自己的脑子有毛病"]

FACTOR_DEFS = {
    "躯体化": {"ids": [1, 4, 12, 27, 40, 42, 48, 49, 52, 53, 56, 58], "desc": "反映身体不适感，如头痛、心悸、肌肉酸痛及各种疼痛。"},
    "强迫症状": {"ids": [3, 9, 10, 28, 38, 45, 46, 51, 55, 65], "desc": "反映难以摆脱的无意义思想、冲动、行为，以及认知障碍。"},
    "人际敏感": {"ids": [6, 21, 34, 36, 37, 41, 61, 69, 73], "desc": "反映社交中的不自在感、自卑感及对他人的评价敏感。"},
    "抑郁": {"ids": [5, 14, 15, 20, 22, 26, 29, 30, 31, 32, 54, 71, 79], "desc": "反映情绪低落、悲观、生活兴趣减退及动力下降。"},
    "焦虑": {"ids": [2, 17, 23, 33, 39, 57, 72, 78, 80, 86], "desc": "反映神经过敏、紧张、烦躁、恐惧感及躯体焦虑表现。"},
    "敌对": {"ids": [11, 24, 63, 67, 74, 81], "desc": "反映愤怒和冲动控制。包括烦恼、爆发脾气、争论及伤害冲动。"},
    "恐怖": {"ids": [13, 25, 47, 50, 70, 75, 82], "desc": "反映对特定环境（如空旷场所、人群、交通工具）的非理性恐惧。"},
    "偏执": {"ids": [8, 18, 43, 68, 76, 83], "desc": "反映思维倾向。包括猜疑、受骗感、不信任感及思维狭隘。"},
    "精神病性": {"ids": [7, 16, 35, 62, 77, 84, 85, 87, 88, 90], "desc": "反映孤独感、被动体验、以及幻觉或特殊的思维逻辑。"},
    "其他": {"ids": [19, 44, 59, 60, 64, 66, 89], "desc": "反映基础生理功能，如近期睡眠质量与饮食状况。"},
}


def json_response(handler, status, payload, extra_headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, str(value))
    handler.end_headers()
    handler.wfile.write(body)


def build_factor_results(scores):
    results = []
    for name, definition in FACTOR_DEFS.items():
        factor_sum = sum(scores[qid] for qid in definition['ids'])
        avg = round(factor_sum / len(definition['ids']), 2)
        results.append({
            'name': name,
            'avg': avg,
            'status': '需关注' if avg >= 2.0 else '正常',
            'desc': definition['desc'],
            'isHigh': avg >= 2.0,
        })
    return results


def build_csv_content(scores, factor_results):
    buffer = io.StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer)
    writer.writerow(['【维度因子分析】'])
    writer.writerow(['维度名称', '因子分', '评估结论'])
    for item in factor_results:
        writer.writerow([item['name'], f"{item['avg']:.2f}", item['status']])
    writer.writerow([])
    writer.writerow(['【90项原始答卷详情】'])
    writer.writerow(['题号', '条目内容', '所属维度', '得分'])
    for index in range(1, 91):
        dimension = '其他'
        for name, definition in FACTOR_DEFS.items():
            if index in definition['ids']:
                dimension = name
                break
        writer.writerow([index, QUESTIONS[index - 1], dimension, scores[index]])
    return buffer.getvalue()


def get_csv_filename(now=None):
    now = now or datetime.now()
    return f"SCL90测评报告_{now.strftime('%Y-%m-%d')}.csv"


def build_mail_text(total, pos_count, avg, factor_results, submitted_at):
    highlighted = [f"{item['name']} {item['avg']:.2f}" for item in factor_results if item['isHigh']]
    focus = '；'.join(highlighted) if highlighted else '本次各维度因子分均在参考范围内'
    return '\n'.join([
        '您好，咨询师：',
        '',
        '以下是来自 SCL-90 在线测评页面的一份新报告。',
        f'提交时间：{submitted_at}',
        f'总分：{total}',
        f'阳性项数：{pos_count}',
        f'总均分：{avg:.2f}',
        f'重点关注维度：{focus}',
        '',
        '详细结果请见附件 CSV。',
    ])


def send_email(csv_content, text_body):
    if MOCK_EMAIL:
        return f'mock-{int(time.time())}'

    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_FROM):
        raise RuntimeError('Missing SMTP configuration. Set SMTP_HOST, SMTP_USER, SMTP_PASS, and SMTP_FROM.')

    message = EmailMessage()
    message['Subject'] = f"SCL-90 测评结果 {datetime.now().strftime('%Y-%m-%d')}"
    message['From'] = SMTP_FROM
    message['To'] = COUNSELOR_EMAIL
    message.set_content(text_body)
    message.add_attachment(
        csv_content.encode('utf-8'),
        maintype='text',
        subtype='csv',
        filename=get_csv_filename(),
    )

    if SMTP_USE_TLS:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(message)
    else:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(message)

    return message['Message-ID'] or f'smtp-{int(time.time())}'


def get_client_ip(handler):
    forwarded = handler.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return handler.client_address[0]


def check_rate_limit(client_ip):
    now = time.time()
    timestamps = [ts for ts in RATE_LIMIT_STORE.get(client_ip, []) if now - ts <= RATE_LIMIT_WINDOW_SECONDS]
    if len(timestamps) >= RATE_LIMIT_MAX:
        RATE_LIMIT_STORE[client_ip] = timestamps
        retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - timestamps[0])))
        return False, retry_after
    timestamps.append(now)
    RATE_LIMIT_STORE[client_ip] = timestamps
    return True, None


def validate_payload(payload):
    if payload.get('trap'):
        return False, 400, '检测到异常提交，请刷新页面后重试。', None

    if payload.get('consent') is not True:
        return False, 400, '请先勾选同意上传，再发送给咨询师。', None

    answers = payload.get('answers')
    if not isinstance(answers, dict):
        return False, 400, '缺少答卷数据，请重新生成报告后再试。', None

    scores = {}
    total = 0
    pos_count = 0
    for index in range(1, 91):
        raw = answers.get(str(index), answers.get(index))
        try:
            score = int(raw)
        except (TypeError, ValueError):
            return False, 400, f'第 {index} 题得分无效，请重新填写后再试。', None
        if score < 1 or score > 5:
            return False, 400, f'第 {index} 题得分无效，请重新填写后再试。', None
        scores[index] = score
        total += score
        if score >= 2:
            pos_count += 1

    avg = round(total / 90, 2)
    if int(payload.get('total', -1)) != total or int(payload.get('posCount', -1)) != pos_count:
        return False, 400, '报告摘要与原始答卷不一致，请重新生成报告后再试。', None

    try:
        payload_avg = round(float(payload.get('avg', -1)), 2)
    except (TypeError, ValueError):
        return False, 400, '报告均分校验失败，请重新生成报告后再试。', None

    if abs(payload_avg - avg) > 0.01:
        return False, 400, '报告均分校验失败，请重新生成报告后再试。', None

    try:
        started_at = int(payload.get('startedAt', 0))
    except (TypeError, ValueError):
        started_at = 0
    if started_at <= 0 or (time.time() * 1000 - started_at) < MIN_COMPLETION_SECONDS * 1000:
        return False, 400, '提交过快，系统已拦截。请稍后重新确认后再发送。', None

    return True, 200, '', {'scores': scores, 'total': total, 'posCount': pos_count, 'avg': avg}


class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            content = (ROOT / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == '/README.md':
            content = (ROOT / 'README.md').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/markdown; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == '/api/health':
            return json_response(self, 200, {'ok': True, 'service': 'scl-90-mailer'})
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/send-report':
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', '0') or 0)
        if content_length <= 0 or content_length > MAX_PAYLOAD_BYTES:
            return json_response(self, 400, {'ok': False, 'message': '请求体无效或过大，请重试。'})

        allowed, retry_after = check_rate_limit(get_client_ip(self))
        if not allowed:
            return json_response(
                self,
                429,
                {'ok': False, 'message': f'发送过于频繁，请在 {max(1, retry_after // 60)} 分钟后重试。'},
                {'Retry-After': retry_after},
            )

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError:
            return json_response(self, 400, {'ok': False, 'message': '请求格式错误，请重试。'})

        ok, status, message, validated = validate_payload(payload)
        if not ok:
            return json_response(self, status, {'ok': False, 'message': message})

        factor_results = build_factor_results(validated['scores'])
        csv_content = build_csv_content(validated['scores'], factor_results)
        text_body = build_mail_text(
            validated['total'],
            validated['posCount'],
            validated['avg'],
            factor_results,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

        try:
            message_id = send_email(csv_content, text_body)
        except Exception as exc:  # noqa: BLE001
            print(f'Failed to send report email: {exc}')
            return json_response(self, 500, {
                'ok': False,
                'message': '云端自动发送失败。请下载 CSV 后人工发送给咨询师，或稍后重试。',
            })

        return json_response(self, 200, {
            'ok': True,
            'counselorEmail': COUNSELOR_EMAIL,
            'message': f'报告已自动发送到咨询师邮箱 {COUNSELOR_EMAIL}。',
            'messageId': message_id,
        })


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f'SCL-90 app listening on http://localhost:{PORT}')
    server.serve_forever()
