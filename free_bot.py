# -*- coding: utf-8 -*-
"""
UZERON FREE BOT - FIXED VERSION
Key fixes:
1. OTP expiry: Bot's API_ID/HASH cannot be used to sign in regular user accounts.
   Users must provide their own API_ID + API_HASH (same as original Zepto bot).
   We also pass phone_code_hash explicitly to prevent expiry.
2. Branding: Apply branding with the LIVE login client BEFORE disconnecting.
"""

import os
import sys
import asyncio
import psycopg2
import json
import pytz
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError,
    PhoneCodeExpiredError, PhoneCodeInvalidError
)
from telethon.tl.functions.account import UpdateProfileRequest
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL     = os.getenv('DATABASE_URL')
BOT_API_ID       = int(os.getenv('API_ID'))
BOT_API_HASH     = os.getenv('API_HASH')
FREE_BOT_TOKEN   = os.getenv('FREE_BOT_TOKEN')
LOGGER_BOT_TOKEN = os.getenv('LOGGER_BOT_TOKEN')
ADMINS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

SUPPORT_LINK     = "https://t.me/Uzeron_Ads_support"
CONTACT_USERNAME = "@Pandaysubscription"
PREMIUM_BOT      = "@Uzeron_AdsBot"
IST = pytz.timezone('Asia/Kolkata')

FREE_MAX_GROUPS          = 100
FREE_CYCLE_DELAY         = 600
FREE_MSG_DELAY           = 60
FREE_MAX_RUNTIME         = 8 * 3600
FREE_BRANDING_LASTNAME   = "• via @Uzeron_AdsBot"
FREE_BRANDING_BIO        = "🚀 Free Automated Ads via @Uzeron_AdsBot | Get Premium: @Pandaysubscription"
FREE_WARNINGS_BEFORE_BAN = 3

# ── Keyboards ──────────────────────────────────────────────────────────────────
def make_keyboard(buttons):
    return {"inline_keyboard": buttons}

def dashboard_keyboard():
    return make_keyboard([
        [{"text": "👤 My Account", "callback_data": "account"},
         {"text": "📊 Status",     "callback_data": "status"}],
        [{"text": "💬 Set Message",              "callback_data": "setmessage"},
         {"text": "⏱️ Delay: 60s | Cycle: 10m",  "callback_data": "delay_info"}],
        [{"text": "🚀 Start Campaign", "callback_data": "startcampaign"},
         {"text": "🛑 Stop Campaign",  "callback_data": "stopcampaign"}],
        [{"text": "🔑 Login",           "callback_data": "login"},
         {"text": "💎 Upgrade Premium", "callback_data": "upgrade"}],
        [{"text": "🚪 Logout", "callback_data": "logout"}]
    ])

def welcome_keyboard():
    return make_keyboard([
        [{"text": "🆓 Use Free Bot", "callback_data": "free_info"}],
        [{"text": "💎 Get Premium",  "callback_data": "upgrade"},
         {"text": "📢 Support",      "url": SUPPORT_LINK}]
    ])

def back_keyboard():
    return make_keyboard([[{"text": "🏠 Dashboard", "callback_data": "dashboard"}]])

def upgrade_keyboard():
    return make_keyboard([
        [{"text": f"💎 Upgrade Now → {CONTACT_USERNAME}",
          "url": "https://t.me/Pandaysubscription"}],
        [{"text": "📢 Support Channel", "url": SUPPORT_LINK}],
        [{"text": "🔙 Back", "callback_data": "dashboard"}]
    ])

def bot_api(method, data=None):
    url = f"https://api.telegram.org/bot{FREE_BOT_TOKEN}/{method}"
    try:
        processed = {k: json.dumps(v) if isinstance(v, dict) else v
                     for k, v in (data or {}).items()}
        requests.post(url, data=processed, timeout=10)
    except Exception as e:
        print(f"Bot API error [{method}]: {e}")

def send_msg(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)
    bot_api("sendMessage", data)

def edit_msg(chat_id, msg_id, text, keyboard=None):
    data = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)
    bot_api("editMessageText", data)

# ── Message templates ──────────────────────────────────────────────────────────
def welcome_text():
    return (
        "🆓 <b>UZERON ADSBOT — Free Plan</b>\n\n"
        "╔══════════════════════╗\n"
        "║ ✦ 100 Groups Max\n║ ✦ 60s Message Delay\n"
        "║ ✦ 10min Cycle Delay\n║ ✦ 8 Hours Daily Runtime\n"
        "║ ✦ Account Branding Required\n"
        "╚══════════════════════╝\n\n"
        "💎 <b>Upgrade to Premium for:</b>\n"
        "• Unlimited groups & runtime\n• Custom delays\n"
        "• No branding\n• Message rotation\n• Auto schedule\n\n"
        "Use /start to open your dashboard"
    )

def dashboard_text(user, runtime_used):
    phone      = user[1] if user and user[1] else "Not connected"
    msg_status = "✅ Set"   if user and user[5] else "❌ Not set"
    campaign   = "🟢 Live" if user and user[6] else "🔴 Stopped"
    hours_used = runtime_used / 3600
    hours_left = max(0, 8 - hours_used)
    return (
        "⚡ <b>UZERON ADSBOT — Free Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Account:</b> <code>{phone}</code>\n"
        f"💬 <b>Ad Message:</b> {msg_status}\n"
        f"⏱️ <b>Delay:</b> 60s | <b>Cycle:</b> 10m\n"
        f"⏳ <b>Runtime Today:</b> {hours_used:.1f}h / 8h\n"
        f"🕐 <b>Time Left:</b> {hours_left:.1f}h\n"
        f"📡 <b>Campaign:</b> {campaign}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Free plan: 100 groups, 8hr/day limit</i>"
    )

def upgrade_text():
    return (
        "💎 <b>UPGRADE TO PREMIUM</b>\n\n"
        "╔══════════════════════╗\n"
        "║ 🚀 Unlimited Groups\n║ ⏱️ Custom Delays\n"
        "║ 🔀 Message Rotation\n║ ⏰ Auto Schedule\n"
        "║ 🏷️ No Branding\n║ 📊 Analytics\n"
        "╚══════════════════════╝\n\n"
        f"👤 Contact: <b>{CONTACT_USERNAME}</b>\n"
        f"🤖 Premium Bot: <b>{PREMIUM_BOT}</b>"
    )

# ── Database ───────────────────────────────────────────────────────────────────
class Database:
    def get_conn(self):
        return psycopg2.connect(DATABASE_URL, sslmode='require')

    def init_db(self):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS free_users (
            user_id BIGINT PRIMARY KEY, username TEXT, phone TEXT,
            api_id INTEGER, api_hash TEXT, session_string TEXT,
            promo_message TEXT, is_active INTEGER DEFAULT 0,
            runtime_today INTEGER DEFAULT 0, last_reset TEXT,
            warning_count INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0,
            branding_set INTEGER DEFAULT 0, created_at TEXT)''')
        conn.commit(); conn.close()

    def get_user(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('''SELECT user_id, phone, api_id, api_hash, session_string,
                            promo_message, is_active, runtime_today, last_reset,
                            warning_count, is_banned, branding_set
                     FROM free_users WHERE user_id=%s''', (user_id,))
        r = c.fetchone(); conn.close(); return r

    def register_user(self, user_id, username):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT user_id FROM free_users WHERE user_id=%s', (user_id,))
        if not c.fetchone():
            c.execute('INSERT INTO free_users (user_id,username,created_at) VALUES (%s,%s,%s)',
                      (user_id, username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit(); conn.close()

    def is_banned(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT is_banned FROM free_users WHERE user_id=%s', (user_id,))
        r = c.fetchone(); conn.close(); return r and r[0] == 1

    def save_session(self, user_id, phone, api_id, api_hash, session_string):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET phone=%s,api_id=%s,api_hash=%s,session_string=%s WHERE user_id=%s',
                  (phone, api_id, api_hash, session_string, user_id))
        conn.commit(); conn.close()

    def set_promo_message(self, user_id, message):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET promo_message=%s WHERE user_id=%s', (message, user_id))
        conn.commit(); conn.close()

    def set_campaign_status(self, user_id, status):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET is_active=%s WHERE user_id=%s', (status, user_id))
        conn.commit(); conn.close()

    def get_runtime_today(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT runtime_today, last_reset FROM free_users WHERE user_id=%s', (user_id,))
        r = c.fetchone(); conn.close()
        if not r: return 0
        runtime, last_reset = r
        today = datetime.now(IST).strftime('%Y-%m-%d')
        if last_reset != today:
            self.reset_runtime(user_id, today); return 0
        return runtime or 0

    def reset_runtime(self, user_id, today):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET runtime_today=0,last_reset=%s WHERE user_id=%s', (today, user_id))
        conn.commit(); conn.close()

    def add_runtime(self, user_id, seconds):
        conn = self.get_conn(); c = conn.cursor()
        today = datetime.now(IST).strftime('%Y-%m-%d')
        c.execute('UPDATE free_users SET runtime_today=COALESCE(runtime_today,0)+%s,last_reset=%s WHERE user_id=%s',
                  (seconds, today, user_id))
        conn.commit(); conn.close()

    def set_branding(self, user_id, status):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET branding_set=%s WHERE user_id=%s', (status, user_id))
        conn.commit(); conn.close()

    def add_warning(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET warning_count=COALESCE(warning_count,0)+1 WHERE user_id=%s', (user_id,))
        c.execute('SELECT warning_count FROM free_users WHERE user_id=%s', (user_id,))
        count = c.fetchone()[0]
        if count >= FREE_WARNINGS_BEFORE_BAN:
            c.execute('UPDATE free_users SET is_banned=1 WHERE user_id=%s', (user_id,))
        conn.commit(); conn.close(); return count

    def ban_user(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET is_banned=1 WHERE user_id=%s', (user_id,))
        conn.commit(); conn.close()

    def logout_user(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET phone=NULL,api_id=NULL,api_hash=NULL,session_string=NULL,is_active=0,branding_set=0 WHERE user_id=%s', (user_id,))
        conn.commit(); conn.close()

    def get_all_users(self):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT user_id, username FROM free_users WHERE is_banned=0')
        r = c.fetchall(); conn.close(); return r

# ── Logger ─────────────────────────────────────────────────────────────────────
class Logger:
    def __init__(self, token):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"

    def send_log(self, chat_id, message):
        try:
            requests.post(self.url, data={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}, timeout=10)
        except Exception as e:
            print(f"Logger error: {e}")

# ── Main bot ───────────────────────────────────────────────────────────────────
class UzeronFreeBot:
    def __init__(self):
        self.bot    = TelegramClient('free_bot', BOT_API_ID, BOT_API_HASH)
        self.db     = Database()
        self.logger = Logger(LOGGER_BOT_TOKEN)
        self.tasks  = {}
        self.login_states    = {}
        self.pending_message = {}
        self.campaign_start_times = {}

    async def start(self):
        self.db.init_db()
        await self.bot.start(bot_token=FREE_BOT_TOKEN)
        print("✓ Uzeron Free Bot started")
        self.register_handlers()
        asyncio.create_task(self.branding_checker())
        print("✓ Live!")
        await self.bot.run_until_disconnected()

    # ── Branding checker ────────────────────────────────────────────────────────
    async def branding_checker(self):
        while True:
            await asyncio.sleep(1800)
            try:
                for uid, _ in self.db.get_all_users():
                    user = self.db.get_user(uid)
                    if user and user[4] and user[11]:
                        asyncio.create_task(self.verify_branding(uid, user))
            except Exception as e:
                print(f"Branding checker error: {e}")

    async def verify_branding(self, uid, user):
        client = None
        try:
            client = TelegramClient(StringSession(user[4]), user[2], user[3])
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect(); return

            me = await client.get_me()
            if FREE_BRANDING_LASTNAME not in (me.last_name or ''):
                count     = self.db.add_warning(uid)
                remaining = FREE_WARNINGS_BEFORE_BAN - count
                if count >= FREE_WARNINGS_BEFORE_BAN:
                    if uid in self.tasks:
                        self.tasks[uid].cancel(); del self.tasks[uid]
                    self.db.set_campaign_status(uid, 0)
                    await client.disconnect()
                    send_msg(uid,
                             "🚫 <b>Banned from Free Tier!</b>\n\n"
                             "Removed branding 3 times.\n"
                             f"Upgrade to continue: {CONTACT_USERNAME}",
                             upgrade_keyboard())
                    return
                await self._do_branding(client, uid)
                await client.disconnect()
                send_msg(uid,
                         f"⚠️ <b>Warning {count}/{FREE_WARNINGS_BEFORE_BAN}</b>\n"
                         f"Branding removed & re-added. {remaining} warning(s) left!",
                         upgrade_keyboard())
            else:
                await client.disconnect()
        except Exception as e:
            print(f"verify_branding uid={uid}: {e}")
            if client:
                try: await client.disconnect()
                except: pass

    async def _do_branding(self, client, uid):
        """Apply last name + bio on an already-connected authorized client."""
        try:
            me       = await client.get_me()
            cur_last = me.last_name or ''
            if FREE_BRANDING_LASTNAME in cur_last:
                self.db.set_branding(uid, 1); return True
            new_last = f"{cur_last} {FREE_BRANDING_LASTNAME}".strip()
            if len(new_last) > 64:
                new_last = FREE_BRANDING_LASTNAME
            await client(UpdateProfileRequest(last_name=new_last, about=FREE_BRANDING_BIO))
            self.db.set_branding(uid, 1); return True
        except Exception as e:
            print(f"_do_branding uid={uid}: {e}"); return False

    # ── Handlers ────────────────────────────────────────────────────────────────
    def register_handlers(self):

        @self.bot.on(events.NewMessage(pattern='/users'))
        async def cmd_users(event):
            if event.sender_id not in ADMINS: return
            lst = self.db.get_all_users()
            msg = f"👥 <b>Free Users ({len(lst)}):</b>\n\n" + \
                  ''.join(f"• {'@'+u if u else 'ID:'+str(i)}\n" for i, u in lst)
            await event.reply(msg or "No users", parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/ban'))
        async def cmd_ban(event):
            if event.sender_id not in ADMINS: return
            try:
                uid = int(event.message.text.split()[1])
                self.db.ban_user(uid)
                if uid in self.tasks: self.tasks[uid].cancel(); del self.tasks[uid]
                await event.reply(f"✅ Banned {uid}")
                send_msg(uid, f"🚫 Banned. Contact {CONTACT_USERNAME}", upgrade_keyboard())
            except: await event.reply("❌ Usage: /ban USER_ID")

        @self.bot.on(events.NewMessage(pattern='/stats'))
        async def cmd_stats(event):
            if event.sender_id not in ADMINS: return
            await event.reply(
                f"📊 Users: {len(self.db.get_all_users())} | Running: {len(self.tasks)}",
                parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def cmd_start(event):
            uid = event.sender_id
            if self.db.is_banned(uid):
                send_msg(uid, "🚫 Banned. Upgrade to continue.", upgrade_keyboard()); return
            self.db.register_user(uid, event.sender.username)
            user    = self.db.get_user(uid)
            runtime = self.db.get_runtime_today(uid)
            send_msg(uid, dashboard_text(user, runtime), dashboard_keyboard())

        @self.bot.on(events.CallbackQuery())
        async def callbacks(event):
            uid  = event.sender_id
            data = event.data.decode()
            await event.answer()
            mid  = event.query.msg_id
            if self.db.is_banned(uid):
                await event.answer("🚫 Banned!", alert=True); return

            user    = self.db.get_user(uid)
            runtime = self.db.get_runtime_today(uid) if user else 0

            if data == 'dashboard':
                edit_msg(uid, mid, dashboard_text(user, runtime), dashboard_keyboard())
            elif data == 'free_info':
                edit_msg(uid, mid, welcome_text(), welcome_keyboard())
            elif data == 'upgrade':
                edit_msg(uid, mid, upgrade_text(), upgrade_keyboard())
            elif data == 'delay_info':
                await event.answer("⏱️ 60s message delay, 10min cycle. Upgrade for custom!", alert=True)
            elif data == 'account':
                phone    = user[1] if user and user[1] else "Not connected"
                conn_str = "✅ Connected" if user and user[4] else "❌ Not connected"
                brand    = "✅ Set" if user and user[11] else "⏳ Pending"
                edit_msg(uid, mid,
                         f"👤 <b>My Account</b>\n\n"
                         f"📱 Phone: <code>{phone}</code>\n"
                         f"🔗 Status: {conn_str}\n🏷️ Branding: {brand}",
                         make_keyboard([
                             [{"text": "🔑 Login", "callback_data": "login"},
                              {"text": "🚪 Logout", "callback_data": "logout"}],
                             [{"text": "🏠 Dashboard", "callback_data": "dashboard"}]
                         ]))
            elif data == 'status':
                s = "🟢 Live" if user and user[6] else "🔴 Stopped"
                preview = (user[5][:60]+'...') if user and user[5] and len(user[5])>60 \
                          else (user[5] if user else "Not set") or "Not set"
                edit_msg(uid, mid,
                         f"📊 <b>Status</b>\n\n"
                         f"📱 {user[1] if user and user[1] else 'Not set'}\n"
                         f"💬 {preview}\n📡 {s}\n"
                         f"⏳ {runtime/3600:.1f}h / 8h",
                         back_keyboard())
            elif data == 'setmessage':
                self.pending_message[uid] = True
                edit_msg(uid, mid,
                         "💬 <b>Set Ad Message</b>\n\nSend message now:\n<i>/cancel to back</i>",
                         make_keyboard([[{"text": "❌ Cancel", "callback_data": "dashboard"}]]))
            elif data == 'startcampaign':
                if not user or not user[4]:
                    await event.answer("❌ Login first!", alert=True); return
                if not user[5]:
                    await event.answer("❌ Set ad message first!", alert=True); return
                if uid in self.tasks:
                    await event.answer("⚠️ Already running!", alert=True); return
                runtime = self.db.get_runtime_today(uid)
                if runtime >= FREE_MAX_RUNTIME:
                    edit_msg(uid, mid, "⏰ Daily limit reached! Upgrade for unlimited.",
                             upgrade_keyboard()); return
                self.db.set_campaign_status(uid, 1)
                self.campaign_start_times[uid] = datetime.now()
                self.tasks[uid] = asyncio.create_task(self.run_campaign(uid))
                self.logger.send_log(uid, f"🆓 Campaign started: {user[1]}")
                edit_msg(uid, mid, dashboard_text(self.db.get_user(uid), runtime), dashboard_keyboard())
                send_msg(uid, f"🚀 <b>Campaign Started!</b>\n{FREE_MAX_GROUPS} groups | {FREE_MSG_DELAY}s delay")
            elif data == 'stopcampaign':
                if uid not in self.tasks:
                    await event.answer("⚠️ Not running!", alert=True); return
                self.db.set_campaign_status(uid, 0)
                self.tasks[uid].cancel(); del self.tasks[uid]
                if uid in self.campaign_start_times:
                    elapsed = (datetime.now()-self.campaign_start_times[uid]).total_seconds()
                    self.db.add_runtime(uid, int(elapsed)); del self.campaign_start_times[uid]
                edit_msg(uid, mid, dashboard_text(self.db.get_user(uid), self.db.get_runtime_today(uid)), dashboard_keyboard())
                send_msg(uid, "🛑 <b>Campaign Stopped!</b>")
            elif data == 'login':
                if user and user[4]:
                    await event.answer("✅ Already logged in!", alert=True); return
                # ── FIX: must collect user's own API_ID + API_HASH first ──
                self.login_states[uid] = {'step': 'waiting_api_id'}
                edit_msg(uid, mid,
                         "🔑 <b>Login — Step 1/4</b>\n\n"
                         "Enter your <b>API ID</b> (numbers only).\n\n"
                         "📌 Get from <a href='https://my.telegram.org'>my.telegram.org</a>\n"
                         "→ API Development Tools\n\n"
                         "<i>/cancel to go back</i>",
                         make_keyboard([[{"text": "❌ Cancel", "callback_data": "cancel_login"}]]))
            elif data == 'cancel_login':
                if uid in self.login_states:
                    try:
                        c = self.login_states[uid].get('client')
                        if c: await c.disconnect()
                    except: pass
                    del self.login_states[uid]
                edit_msg(uid, mid, dashboard_text(user, runtime), dashboard_keyboard())
            elif data == 'logout':
                if uid in self.tasks: self.tasks[uid].cancel(); del self.tasks[uid]
                self.db.logout_user(uid)
                edit_msg(uid, mid, dashboard_text(self.db.get_user(uid), 0), dashboard_keyboard())
                send_msg(uid, "✅ <b>Logged out!</b>")

        @self.bot.on(events.NewMessage())
        async def global_handler(event):
            uid  = event.sender_id
            text = event.message.text
            if not text or self.db.is_banned(uid): return

            if text.strip() == '/cancel':
                if uid in self.pending_message: del self.pending_message[uid]
                if uid in self.login_states:
                    try:
                        c = self.login_states[uid].get('client')
                        if c: await c.disconnect()
                    except: pass
                    del self.login_states[uid]
                user    = self.db.get_user(uid)
                runtime = self.db.get_runtime_today(uid) if user else 0
                send_msg(uid, dashboard_text(user, runtime), dashboard_keyboard())
                return

            if uid in self.pending_message and not text.startswith('/'):
                del self.pending_message[uid]
                self.db.set_promo_message(uid, text)
                send_msg(uid,
                         f"✅ <b>Ad Message Saved!</b>\n\n"
                         f"📝 <i>{text[:100]}{'...' if len(text)>100 else ''}</i>",
                         make_keyboard([
                             [{"text": "🚀 Start Campaign", "callback_data": "startcampaign"}],
                             [{"text": "🏠 Dashboard",      "callback_data": "dashboard"}]
                         ]))
                return

            if uid in self.login_states:
                await self.handle_login(uid, text)

    # ── Login state machine ─────────────────────────────────────────────────────
    async def handle_login(self, uid, text):
        if text.startswith('/'): return
        state = self.login_states[uid]
        step  = state['step']

        # Step 1 — API ID
        if step == 'waiting_api_id':
            if not text.strip().isdigit():
                send_msg(uid, "❌ API ID must be numbers only. Try again:"); return
            state['api_id'] = int(text.strip())
            state['step']   = 'waiting_api_hash'
            send_msg(uid,
                     "🔑 <b>Login — Step 2/4</b>\n\n"
                     "Now enter your <b>API Hash</b> (32-char string from my.telegram.org):\n\n"
                     "<i>/cancel to go back</i>")

        # Step 2 — API Hash
        elif step == 'waiting_api_hash':
            if len(text.strip()) < 10:
                send_msg(uid, "❌ API Hash looks too short. Paste it exactly:"); return
            state['api_hash'] = text.strip()
            state['step']     = 'waiting_phone'
            send_msg(uid,
                     "🔑 <b>Login — Step 3/4</b>\n\n"
                     "Send your <b>phone number</b> with country code:\n"
                     "Example: <code>+917239879045</code>\n\n"
                     "<i>/cancel to go back</i>")

        # Step 3 — Phone number → send OTP
        elif step == 'waiting_phone':
            if not text.strip().startswith('+'):
                send_msg(uid, "❌ Must start with +. Example: <code>+917239879045</code>"); return
            phone    = text.strip()
            api_id   = state['api_id']
            api_hash = state['api_hash']
            client   = None
            try:
                client = TelegramClient(StringSession(), api_id, api_hash)
                await client.connect()
                result = await client.send_code_request(phone)
                state['client']          = client
                state['phone']           = phone
                state['phone_code_hash'] = result.phone_code_hash  # ← KEY FIX
                state['step']            = 'waiting_code'
                send_msg(uid,
                         "📨 <b>Login — Step 4/4</b>\n\n"
                         "Code sent! Enter it now (you have ~60 seconds):\n\n"
                         "<i>/cancel to go back</i>",
                         make_keyboard([[{"text": "❌ Cancel", "callback_data": "cancel_login"}]]))
            except Exception as e:
                send_msg(uid, f"❌ Failed to send code: <code>{e}</code>\n\nTry /cancel and start over.")
                if client:
                    try: await client.disconnect()
                    except: pass
                if uid in self.login_states: del self.login_states[uid]

        # Step 4 — OTP code
        elif step == 'waiting_code':
            code = text.replace(' ', '').replace('-', '')
            if not code.isdigit():
                send_msg(uid, "❌ Digits only please:"); return
            try:
                # Must pass phone_code_hash — without it Telegram rejects as expired
                await state['client'].sign_in(
                    phone=state['phone'],
                    code=code,
                    phone_code_hash=state['phone_code_hash']
                )
                await self._complete_login(uid, state)
            except PhoneCodeExpiredError:
                send_msg(uid,
                         "❌ <b>Code expired!</b>\n\n"
                         "Codes are valid for ~60 seconds only.\n"
                         "Please tap /cancel then Login again to get a fresh code.")
                try: await state['client'].disconnect()
                except: pass
                if uid in self.login_states: del self.login_states[uid]
            except PhoneCodeInvalidError:
                send_msg(uid, "❌ Wrong code. Check and try again:")
            except SessionPasswordNeededError:
                state['step'] = 'waiting_password'
                send_msg(uid,
                         "🔐 <b>2FA Required</b>\n\nEnter your 2FA password:",
                         make_keyboard([[{"text": "❌ Cancel", "callback_data": "cancel_login"}]]))
            except Exception as e:
                send_msg(uid, f"❌ Error: <code>{e}</code>\n\n/cancel and try again.")
                try: await state['client'].disconnect()
                except: pass
                if uid in self.login_states: del self.login_states[uid]

        # Step 4b — 2FA password
        elif step == 'waiting_password':
            try:
                await state['client'].sign_in(password=text)
                await self._complete_login(uid, state)
            except Exception as e:
                send_msg(uid, f"❌ 2FA failed: <code>{e}</code>\n\nTry again:")

    async def _complete_login(self, uid, state):
        """
        KEY FIX: Apply branding using the LIVE login client BEFORE disconnecting.
        This is the only way to guarantee Telegram accepts UpdateProfileRequest.
        """
        client = state['client']
        phone  = state['phone']

        send_msg(uid,
                 f"✅ <b>Login Successful!</b>\n\n"
                 f"📱 Account: <code>{phone}</code>\n\n"
                 "🏷️ Applying branding to your account now...")

        # ── Apply branding FIRST while client is live & authorized ──
        branding_ok = await self._do_branding(client, uid)

        # Save session (client still connected)
        session_str = client.session.save()

        # Now disconnect
        try: await client.disconnect()
        except: pass

        # Save to DB
        self.db.save_session(uid, phone, state['api_id'], state['api_hash'], session_str)
        if uid in self.login_states: del self.login_states[uid]
        self.logger.send_log(uid, f"✅ Login: {phone}")

        if branding_ok:
            send_msg(uid,
                     "✅ <b>Account Setup Complete!</b>\n\n"
                     f"🏷️ Added to your last name:\n<code>{FREE_BRANDING_LASTNAME}</code>\n\n"
                     "⚠️ Do NOT remove this. 3 removals = permanent ban.\n"
                     "💎 Upgrade to remove branding requirement!",
                     make_keyboard([
                         [{"text": "💬 Set Ad Message", "callback_data": "setmessage"}],
                         [{"text": "🏠 Dashboard",      "callback_data": "dashboard"}]
                     ]))
        else:
            send_msg(uid,
                     "✅ <b>Login Successful!</b>\n\n"
                     "⚠️ Could not auto-set branding.\n"
                     f"Manually add to your last name:\n<code>{FREE_BRANDING_LASTNAME}</code>",
                     make_keyboard([[{"text": "🏠 Dashboard", "callback_data": "dashboard"}]]))

    # ── Campaign runner ─────────────────────────────────────────────────────────
    async def run_campaign(self, uid):
        client = None
        try:
            user   = self.db.get_user(uid)
            client = TelegramClient(StringSession(user[4]), user[2], user[3])
            await client.connect()
            if not await client.is_user_authorized():
                send_msg(uid, "❌ Session expired! Logout and login again.")
                self.db.set_campaign_status(uid, 0); return

            dialogs = await client.get_dialogs()
            groups  = [d for d in dialogs if d.is_group][:FREE_MAX_GROUPS]
            if not groups:
                send_msg(uid, "❌ No groups found!"); self.db.set_campaign_status(uid, 0); return

            send_msg(uid, f"📊 <b>Ready!</b> {len(groups)} groups | {FREE_MSG_DELAY}s delay\n🚀 Starting...")

            round_num      = 0
            campaign_start = datetime.now()

            while self.db.get_user(uid)[6]:
                runtime  = self.db.get_runtime_today(uid)
                elapsed  = (datetime.now()-campaign_start).total_seconds()
                total    = runtime + elapsed
                if total >= FREE_MAX_RUNTIME:
                    self.db.set_campaign_status(uid, 0)
                    self.db.add_runtime(uid, int(elapsed))
                    if uid in self.campaign_start_times: del self.campaign_start_times[uid]
                    send_msg(uid, "⏰ <b>8-Hour Limit!</b> Upgrade for unlimited.", upgrade_keyboard())
                    break

                round_num += 1
                sent = failed = 0
                message = self.db.get_user(uid)[5]

                for group in groups:
                    if not self.db.get_user(uid)[6]: break
                    elapsed = (datetime.now()-campaign_start).total_seconds()
                    if runtime + elapsed >= FREE_MAX_RUNTIME: break
                    try:
                        await client.send_message(group.entity, message)
                        sent += 1
                        await asyncio.sleep(FREE_MSG_DELAY)
                    except FloodWaitError as e:
                        send_msg(uid, f"⚠️ FloodWait {e.seconds}s...")
                        await asyncio.sleep(e.seconds)
                    except Exception:
                        failed += 1
                        await asyncio.sleep(10)

                hours_left = max(0, 8 - (runtime+(datetime.now()-campaign_start).total_seconds())/3600)
                send_msg(uid,
                         f"📊 Round {round_num}: ✅{sent} sent | ❌{failed} failed | ⏳{hours_left:.1f}h left\n"
                         f"Next in {FREE_CYCLE_DELAY//60}m...",
                         make_keyboard([[{"text":"🛑 Stop","callback_data":"stopcampaign"},
                                         {"text":"💎 Upgrade","callback_data":"upgrade"}]]))
                await asyncio.sleep(FREE_CYCLE_DELAY)

        except asyncio.CancelledError:
            if uid in self.campaign_start_times:
                elapsed = (datetime.now()-self.campaign_start_times[uid]).total_seconds()
                self.db.add_runtime(uid, int(elapsed)); del self.campaign_start_times[uid]
        except Exception as e:
            print(f"Campaign uid={uid}: {e}")
            self.db.set_campaign_status(uid, 0)
            if uid in self.tasks: del self.tasks[uid]
            try: send_msg(uid, f"❌ Campaign error: <code>{e}</code>")
            except: pass
        finally:
            if client:
                try: await client.disconnect()
                except: pass

# ── Entry point ────────────────────────────────────────────────────────────────
async def main():
    missing = [v for v in ['API_ID','API_HASH','FREE_BOT_TOKEN',
                            'LOGGER_BOT_TOKEN','ADMIN_IDS','DATABASE_URL']
               if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}"); sys.exit(1)
    await UzeronFreeBot().start()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\nStopped")
    except Exception as e: print(f"Fatal: {e}"); sys.exit(1)
