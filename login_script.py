import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta
import aiofiles
import random
import requests
import os

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def format_to_iso(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# 全局浏览器实例
browser = None

# 全局计数器和失败列表
success_count = 0
fail_count = 0
failed_usernames = []

async def login(username, password, panel):
    global browser, success_count, fail_count, failed_usernames

    page = None
    serviceName = 'ct8' if 'ct8' in panel else 'serv00'
    try:
        if not browser:
            browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])

        page = await browser.newPage()
        url = f'https://{panel}/login/?next=/'
        await page.goto(url)

        username_input = await page.querySelector('#id_username')
        if username_input:
            await page.evaluate('''(input) => input.value = ""''', username_input)

        await page.type('#id_username', username)
        await page.type('#id_password', password)

        login_button = await page.querySelector('#submit')
        if login_button:
            await login_button.click()
        else:
            raise Exception('无法找到登录按钮')

        await page.waitForNavigation()

        is_logged_in = await page.evaluate('''() => {
            const logoutButton = document.querySelector('a[href="/logout/"]');
            return logoutButton !== null;
        }''')

        if is_logged_in:
            success_count += 1
        else:
            fail_count += 1
            failed_usernames.append(f"{serviceName}:{username}")

        return is_logged_in

    except Exception as e:
        print(f'{serviceName}账号 {username} 登录时出现错误: {e}')
        fail_count += 1
        failed_usernames.append(f"{serviceName}:{username}")
        return False

    finally:
        if page:
            await page.close()

async def main():
    global success_count, fail_count, failed_usernames
    success_count = 0
    fail_count = 0
    failed_usernames = []

    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        print(f'读取 accounts.json 文件时出错: {e}')
        return

    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        await login(username, password, panel)

        delay = random.randint(1000, 8000)
        await delay_time(delay)
    
    # 准备汇总消息
    now_utc = format_to_iso(datetime.utcnow())
    now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
    summary_message = f"自动化脚本运行汇总 (北京时间 {now_beijing}，UTC时间 {now_utc}):\n"
    summary_message += f"成功登录: {success_count} 个账号\n"
    summary_message += f"失败登录: {fail_count} 个账号\n"
    
    if failed_usernames:
        summary_message += "失败的用户名:\n" + "\n".join(failed_usernames)
    
    await send_telegram_message(summary_message)
    print("登录操作完成，汇总信息已发送到Telegram。")

async def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'reply_markup': {
            'inline_keyboard': [
                [
                    {
                        'text': '问题反馈❓',
                        'url': 'https://t.me/yxjsjl'
                    }
                ]
            ]
        }
    }
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"发送消息到Telegram失败: {response.text}")
    except Exception as e:
        print(f"发送消息到Telegram时出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())
