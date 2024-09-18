import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta
import aiofiles
import random
import aiohttp
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def format_to_iso(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# 全局计数器和失败列表
success_count = 0
fail_count = 0
failed_usernames = []

async def login(browser, username, password, panel):
    global success_count, fail_count, failed_usernames

    page = None
    serviceName = 'ct8' if 'ct8' in panel else 'serv00'
    try:
        logging.info(f'正在尝试登录 {serviceName}:{username}')
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
            logging.info(f'{serviceName}:{username} 登录成功')
        else:
            fail_count += 1
            failed_usernames.append(f"{serviceName}:{username}")
            logging.warning(f'{serviceName}:{username} 登录失败')

        return is_logged_in

    except Exception as e:
        logging.error(f'{serviceName}:{username} 登录时出现错误: {e}')
        fail_count += 1
        failed_usernames.append(f"{serviceName}:{username}")
        return False

    finally:
        if page:
            await page.close()

async def process_account(browser, account):
    username = account['username']
    password = account['password']
    panel = account['panel']

    await login(browser, username, password, panel)

    delay = random.randint(1000, 8000)
    await delay_time(delay)

async def main():
    global success_count, fail_count, failed_usernames
    success_count = 0
    fail_count = 0
    failed_usernames = []

    # 记录开始时间
    start_time = datetime.now()

    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        logging.error(f'读取 accounts.json 文件时出错: {e}')
        return

    try:
        browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        
        # 使用 asyncio.gather 并发处理所有账号
        await asyncio.gather(*(process_account(browser, account) for account in accounts))
    
    except Exception as e:
        logging.error(f'处理账号时出现错误: {e}')
    
    finally:
        if browser:
            await browser.close()

    # 计算总耗时
    end_time = datetime.now()
    total_time = end_time - start_time
    
    # 准备汇总消息
    now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
    summary_message = f"自动化脚本运行汇总 (北京时间 {now_beijing}):\n"
    summary_message += f"成功登录: {success_count} 个账号\n"
    summary_message += f"失败登录: {fail_count} 个账号\n"
    summary_message += f"总耗时: {total_time.total_seconds():.2f} 秒\n"
    
    if failed_usernames:
        summary_message += "失败的用户名:\n" + "\n".join(failed_usernames)
    
    await send_telegram_message(summary_message)
    logging.info("登录操作完成，汇总信息已发送到Telegram。")

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
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"发送消息到Telegram失败: {await response.text()}")
    except Exception as e:
        logging.error(f"发送消息到Telegram时出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())
