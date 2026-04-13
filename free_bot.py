# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import psycopg2
from psycopg2 import extras
import json
import pytz
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, SessionPasswordNeededError
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
BOT_API_ID = int(os.getenv('API_ID'))
BOT_API_HASH = os.getenv('API_HASH')
FREE_BOT_TOKEN = os.getenv('FREE_BOT_TOKEN')
LOGGER_BOT_TOKEN = os.getenv('LOGGER_BOT_TOKEN')
ADMINS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

SUPPORT_LINK = "https://t.me/Uzeron_Ads_support"
CONTACT_USERNAME = "@Pandaysubscription"
PREMIUM_BOT = "@Uzeron_AdsBot"
IST = pytz.timezone('Asia/Kolkata')

# ============================================
# FREE TIER LIMITS
# ============================================
FREE_MAX_GROUPS = 100        # Max groups to send to
FREE_CYCLE_DELAY = 600       # 10 minutes between cycles (seconds)
FREE_MSG_DELAY = 60          # 60 seconds between messages
FREE_MAX_RUNTIME = 8 * 3600  # 8 hours max runtime per day (seconds)
FREE_BRANDING_LASTNAME = "• via @Uzeron_AdsBot"
FREE_BRANDING_BIO = "🚀 Free Automated Ads via @Uzeron_AdsBot | Get Premium: @Pandaysubscription"
FREE_WARNINGS_BEFORE_BAN = 3

# ============================================
# KEYBOARD HELPERS
# ============================================
def make_keyboard(buttons):
    return {"inline_keyboard": buttons}

def dashboard_keyboard():
    return make_keyboard([
        [{"text": "👤 My Account", "callback_data": "account"},
         {"text": "📊 Status", "callback_data": "status"}],
        [{"text": "💬 Set Message", "callback_data": "setmessage"},
         {"text": "⏱️ Delay: 60s | Cycle: 10m", "callback_data": "delay_info"}],
        [{"text": "🚀 Start Campaign", "callback_data": "startcampaign"},
         {"text": "🛑 Stop Campaign", "callback_data": "stopcampaign"}],
        [{"text": "🔑 Login", "callback_data": "login"},
         {"text": "💎 Upgrade Premium", "callback_data": "upgrade"}],
        [{"text": "🚪 Logout", "callback_data": "logout"}]
    ])

def welcome_keyboard():
    return make_keyboard([
        [{"text": "🆓 Use Free Bot", "callback_data": "free_info"}],
        [{"text": "💎 Get Premium", "callback_data": "upgrade"},
         {"text": "📢 Support", "url": SUPPORT_LINK}]
    ])

def back_keyboard():
    return make_keyboard([[{"text": "🏠 Dashboard", "callback_data": "dashboard"}]])

def upgrade_keyboard():
    return make_keyboard([
        [{"text": "💎 Upgrade Now → " + CONTACT_USERNAME,
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
    data = {"chat_id": chat_id, "message_id": msg_id,
            "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)
    bot_api("editMessageText", data)

# ============================================
# MESSAGE TEMPLATES
# ============================================
def welcome_text():
    return (
        "🆓 <b>UZERON ADSBOT — Free Plan</b>\n\n"
        "╔══════════════════════╗\n"
        "║  ✦ 100 Groups Max\n"
        "║  ✦ 60s Message Delay\n"
        "║  ✦ 10min Cycle Delay\n"
        "║  ✦ 8 Hours Daily Runtime\n"
        "║  ✦ Account Branding Required\n"
        "╚══════════════════════╝\n\n"
        "💎 <b>Upgrade to Premium for:</b>\n"
        "• Unlimited groups & runtime\n"
        "• Custom delays\n"
        "• No branding\n"
        "• Message rotation\n"
        "• Auto schedule\n\n"
        "Use /start to open your dashboard"
    )

def dashboard_text(user, runtime_used):
    phone = user[1] if user and user[1] else "Not connected"
    msg_status = "✅ Set" if user and user[5] else "❌ Not set"
    campaign = "🟢 Live" if user and user[6] else "🔴 Stopped"
    hours_used = runtime_used / 3600
    hours_left = max(0, 8 - hours_used)
    return (
        "⚡ <b>UZERON ADSBOT — Free Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Account:</b> <code>{phone}</code>\n"
        f"💬 <b>Ad Message:</b> {msg_status}\n"
        f"⏱️ <b>Delay:</b> 60s  |  <b>Cycle:</b> 10m\n"
        f"⏳ <b>Runtime Today:</b> {hours_used:.1f}h / 8h\n"
        f"🕐 <b>Time Left:</b> {hours_left:.1f}h\n"
        f"📡 <b>Campaign:</b> {campaign}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Free plan: 100 groups, 8hr/day limit</i>"
    )

def upgrade_text():
    return (
        "💎 <b>UPGRADE TO PREMIUM</b>\n\n"
        "Unlock the full power of Uzeron!\n\n"
        "╔══════════════════════╗\n"
        "║  🚀 Unlimited Groups\n"
        "║  ⏱️ Custom Delays (30/45/60s)\n"
        "║  🔀 Message Rotation (3 msgs)\n"
        "║  ⏰ Auto Schedule (IST)\n"
        "║  🏷️ No Account Branding\n"
        "║  📊 Campaign Analytics\n"
        "║  24/7 Priority Support\n"
        "╚══════════════════════╝\n\n"
        "📦 <b>Plans:</b>\n"
        "🥉 Starter — 7 Days\n"
        "🥈 Growth  — 15 Days\n"
        "🥇 Pro     — 30 Days\n\n"
        f"👤 Contact: <b>{CONTACT_USERNAME}</b>\n"
        f"🤖 Premium Bot: <b>{PREMIUM_BOT}</b>"
    )

# ============================================
# DATABASE
# ============================================
class Database:
    def __init__(self):
        self.init_db()

    def get_conn(self):
        return psycopg2.connect(DATABASE_URL, sslmode='require')

    def init_db(self):
        conn = self.get_conn()
        c = conn.cursor()
        # Free users table - separate from premium
        c.execute('''CREATE TABLE IF NOT EXISTS free_users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            phone TEXT,
            api_id INTEGER,
            api_hash TEXT,
            session_string TEXT,
            promo_message TEXT,
            is_active INTEGER DEFAULT 0,
            runtime_today INTEGER DEFAULT 0,
            last_reset TEXT,
            warning_count INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            branding_set INTEGER DEFAULT 0,
            created_at TEXT
        )''')
        conn.commit()
        conn.close()

    def get_user(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('''SELECT user_id, phone, api_id, api_hash, session_string,
                     promo_message, is_active, runtime_today, last_reset,
                     warning_count, is_banned, branding_set
                     FROM free_users WHERE user_id=%s''', (user_id,))
        r = c.fetchone()
        conn.close()
        return r

    def register_user(self, user_id, username):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT user_id FROM free_users WHERE user_id=%s', (user_id,))
        if not c.fetchone():
            c.execute('''INSERT INTO free_users
                        (user_id, username, created_at)
                        VALUES (%s, %s, %s)''',
                     (user_id, username,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
        conn.close()

    def is_banned(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT is_banned FROM free_users WHERE user_id=%s', (user_id,))
        r = c.fetchone()
        conn.close()
        return r and r[0] == 1

    def save_session(self, user_id, phone, api_id, api_hash, session_string):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('''UPDATE free_users SET phone=%s, api_id=%s,
                     api_hash=%s, session_string=%s WHERE user_id=%s''',
                  (phone, api_id, api_hash, session_string, user_id))
        conn.commit()
        conn.close()

    def set_promo_message(self, user_id, message):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE free_users SET promo_message=%s WHERE user_id=%s',
                  (message, user_id))
        conn.commit()
        conn.close()

    def set_campaign_status(self, user_id, status):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE free_users SET is_active=%s WHERE user_id=%s',
                  (status, user_id))
        conn.commit()
        conn.close()

    def get_runtime_today(self, user_id):
        """Get runtime used today, reset if new day"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT runtime_today, last_reset FROM free_users WHERE user_id=%s',
                  (user_id,))
        r = c.fetchone()
        conn.close()
        if not r:
            return 0
        runtime, last_reset = r
        # Reset if new day (IST)
        today = datetime.now(IST).strftime('%Y-%m-%d')
        if last_reset != today:
            self.reset_runtime(user_id, today)
            return 0
        return runtime or 0

    def reset_runtime(self, user_id, today):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE free_users SET runtime_today=0, last_reset=%s WHERE user_id=%s',
                  (today, user_id))
        conn.commit()
        conn.close()

    def add_runtime(self, user_id, seconds):
        conn = self.get_conn()
        c = conn.cursor()
        today = datetime.now(IST).strftime('%Y-%m-%d')
        c.execute('''UPDATE free_users SET
                     runtime_today = COALESCE(runtime_today, 0) + %s,
                     last_reset = %s
                     WHERE user_id=%s''', (seconds, today, user_id))
        conn.commit()
        conn.close()

    def set_branding(self, user_id, status):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE free_users SET branding_set=%s WHERE user_id=%s',
                  (status, user_id))
        conn.commit()
        conn.close()

    def add_warning(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('''UPDATE free_users SET
                     warning_count = COALESCE(warning_count, 0) + 1
                     WHERE user_id=%s''', (user_id,))
        c.execute('SELECT warning_count FROM free_users WHERE user_id=%s', (user_id,))
        count = c.fetchone()[0]
        if count >= FREE_WARNINGS_BEFORE_BAN:
            c.execute('UPDATE free_users SET is_banned=1 WHERE user_id=%s', (user_id,))
        conn.commit()
        conn.close()
        return count

    def ban_user(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('UPDATE free_users SET is_banned=1 WHERE user_id=%s', (user_id,))
        conn.commit()
        conn.close()

    def logout_user(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('''UPDATE free_users SET phone=NULL, api_id=NULL,
                     api_hash=NULL, session_string=NULL,
                     is_active=0, branding_set=0 WHERE user_id=%s''', (user_id,))
        conn.commit()
        conn.close()

    def get_all_users(self):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute('SELECT user_id, username FROM free_users WHERE is_banned=0')
        r = c.fetchall()
        conn.close()
        return r

# ============================================
# LOGGER
# ============================================
class Logger:
    def __init__(self, token):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"

    def send_log(self, chat_id, message):
        try:
            requests.post(self.url,
                data={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
                timeout=10)
        except Exception as e:
            print(f"Logger error: {e}")

# ============================================
# FREE BOT
# ============================================
class UzeronFreeBot:
    def __init__(self):
        self.bot = TelegramClient(StringSession(), BOT_API_ID, BOT_API_HASH)
        self.db = Database()
        self.logger = Logger(LOGGER_BOT_TOKEN)
        self.tasks = {}
        self.login_states = {}
        self.pending_message = {}
        self.campaign_start_times = {}  # Track when campaign started

    async def start(self):
        await self.bot.start(bot_token=FREE_BOT_TOKEN)
        print("✓ Uzeron Free Bot started")
        self.register_handlers()
        # Start branding checker
        asyncio.create_task(self.branding_checker())
        print("✓ Free Bot is live!")
        await self.bot.run_until_disconnected()

    async def branding_checker(self):
        """Check every 30 mins if users still have branding"""
        while True:
            await asyncio.sleep(1800)  # Check every 30 minutes
            try:
                users = self.db.get_all_users()
                for uid, username in users:
                    user = self.db.get_user(uid)
                    if not user or not user[4]:  # No session
                        continue
                    if not user[11]:  # Branding not set yet, skip check
                        continue
                    # Check if branding still exists
                    asyncio.create_task(self.verify_branding(uid, user))
            except Exception as e:
                print(f"Branding checker error: {e}")

    async def verify_branding(self, uid, user):
        """Verify user still has branding on their account"""
        try:
            user_client = TelegramClient(
                StringSession(user[4]), user[2], user[3])
            await user_client.connect()
            me = await user_client.get_me()
            await user_client.disconnect()

            last_name = me.last_name or ""
            bio_ok = True  # We can't easily check bio without extra API call

            if FREE_BRANDING_LASTNAME not in last_name:
                # Branding removed! Add warning
                count = self.db.add_warning(uid)
                warnings_left = FREE_WARNINGS_BEFORE_BAN - count

                if count >= FREE_WARNINGS_BEFORE_BAN:
                    # Ban user
                    if uid in self.tasks:
                        self.tasks[uid].cancel()
                        del self.tasks[uid]
                    self.db.set_campaign_status(uid, 0)
                    send_msg(uid,
                        "🚫 <b>Account Banned from Free Tier!</b>\n\n"
                        "You removed the required branding from your account.\n\n"
                        "After 3 warnings your access has been permanently revoked.\n\n"
                        f"To continue using our service, upgrade to premium:\n"
                        f"👤 {CONTACT_USERNAME}",
                        upgrade_keyboard())
                    self.logger.send_log(uid, f"🚫 User {uid} banned for removing branding")
                else:
                    send_msg(uid,
                        f"⚠️ <b>Warning {count}/{FREE_WARNINGS_BEFORE_BAN} — Branding Removed!</b>\n\n"
                        f"You removed the required last name branding.\n\n"
                        f"Please add back to your last name:\n"
                        f"<code>{FREE_BRANDING_LASTNAME}</code>\n\n"
                        f"⚠️ <b>{warnings_left} warning(s) left before ban!</b>\n\n"
                        f"Or upgrade to remove branding requirement:",
                        upgrade_keyboard())

        except Exception as e:
            print(f"Branding verify error for {uid}: {e}")

    async def set_branding(self, uid, user):
        """Set branding on user's account"""
        try:
            user_client = TelegramClient(
                StringSession(user[4]), user[2], user[3])
            await user_client.connect()
            me = await user_client.get_me()

            # Update last name and bio
            current_last = me.last_name or ""
            if FREE_BRANDING_LASTNAME not in current_last:
                new_last = f"{current_last} {FREE_BRANDING_LASTNAME}".strip()
                # Use raw API call for profile update
                from telethon.tl.functions.account import UpdateProfileRequest as UPR
                await user_client(UPR(
                    last_name=new_last,
                    about=FREE_BRANDING_BIO
                ))

            await user_client.disconnect()
            self.db.set_branding(uid, 1)
            return True
        except Exception as e:
            print(f"Set branding error for {uid}: {e}")
            try: await user_client.disconnect()
            except: pass
            return False

    def register_handlers(self):

        # ── ADMIN COMMANDS ──────────────────────

        @self.bot.on(events.NewMessage(pattern='/addcode'))
        async def addcode(event):
            if event.sender_id not in ADMINS: return
            await event.reply("❌ Use the premium bot to add codes.")

        @self.bot.on(events.NewMessage(pattern='/users'))
        async def users(event):
            if event.sender_id not in ADMINS: return
            users_list = self.db.get_all_users()
            if not users_list:
                await event.reply("👥 No free users yet")
                return
            msg = f"👥 <b>Free Users ({len(users_list)}):</b>\n\n"
            for uid, uname in users_list:
                msg += f"• {'@'+uname if uname else 'ID:'+str(uid)}\n"
            await event.reply(msg, parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/ban'))
        async def ban(event):
            if event.sender_id not in ADMINS: return
            try:
                uid = int(event.message.text.split()[1])
                self.db.ban_user(uid)
                if uid in self.tasks:
                    self.tasks[uid].cancel()
                    del self.tasks[uid]
                await event.reply(f"✅ User {uid} banned from free tier")
                try:
                    send_msg(uid,
                        "🚫 <b>You have been banned from the free tier.</b>\n\n"
                        f"Contact {CONTACT_USERNAME} for more info.",
                        upgrade_keyboard())
                except: pass
            except:
                await event.reply("❌ Usage: /ban USER_ID")

        @self.bot.on(events.NewMessage(pattern='/stats'))
        async def stats(event):
            if event.sender_id not in ADMINS: return
            total = len(self.db.get_all_users())
            running = len(self.tasks)
            await event.reply(
                f"📊 <b>Free Bot Statistics</b>\n\n"
                f"👥 Total Free Users: {total}\n"
                f"🚀 Running Campaigns: {running}",
                parse_mode='html')

        # ── USER COMMANDS ────────────────────────

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start(event):
            uid = event.sender_id
            username = event.sender.username

            # Check if banned
            if self.db.is_banned(uid):
                send_msg(uid,
                    "🚫 <b>You are banned from the free tier.</b>\n\n"
                    "You removed required branding 3 times.\n\n"
                    f"Upgrade to premium to continue:\n{CONTACT_USERNAME}",
                    upgrade_keyboard())
                return

            # Register user
            self.db.register_user(uid, username)
            user = self.db.get_user(uid)
            runtime = self.db.get_runtime_today(uid)
            send_msg(uid, dashboard_text(user, runtime), dashboard_keyboard())

        # ── CALLBACK BUTTONS ─────────────────────

        @self.bot.on(events.CallbackQuery())
        async def callbacks(event):
            uid = event.sender_id
            data = event.data.decode('utf-8')
            await event.answer()
            mid = event.query.msg_id

            if self.db.is_banned(uid):
                await event.answer("🚫 You are banned!", alert=True)
                return

            user = self.db.get_user(uid)
            runtime = self.db.get_runtime_today(uid) if user else 0

            if data == 'dashboard':
                edit_msg(uid, mid, dashboard_text(user, runtime), dashboard_keyboard())

            elif data == 'free_info':
                edit_msg(uid, mid, welcome_text(), welcome_keyboard())

            elif data == 'upgrade':
                edit_msg(uid, mid, upgrade_text(), upgrade_keyboard())

            elif data == 'delay_info':
                await event.answer(
                    "⏱️ Free plan: 60s message delay, 10min cycle delay\n"
                    "Upgrade to Premium for custom delays!",
                    alert=True)

            elif data == 'account':
                phone = user[1] if user and user[1] else "Not connected"
                connected = "✅ Connected" if user and user[4] else "❌ Not connected"
                branding = "✅ Set" if user and user[11] else "⏳ Pending"
                branding = "✅ Set" if user and user[11] else "⏳ Pending"
                edit_msg(uid, mid,
                    f"👤 <b>My Account</b>\n\n"
                    f"📱 Phone: <code>{phone}</code>\n"
                    f"🔗 Status: {connected}\n"
                    f"🏷️ Branding: {branding}",
                    make_keyboard([
                        [{"text": "🔑 Login", "callback_data": "login"},
                         {"text": "🚪 Logout", "callback_data": "logout"}],
                        [{"text": "🏠 Dashboard", "callback_data": "dashboard"}]
                    ]))

            elif data == 'status':
                s = "🟢 Live" if user and user[5] else "🔴 Stopped"
                msg_preview = (user[5][:60]+'...') if user and user[5] and len(user[5]) > 60 else (user[5] if user else "Not set") or "Not set"
                hours_used = runtime / 3600
                edit_msg(uid, mid,
                    f"📊 <b>Campaign Status</b>\n\n"
                    f"📱 Phone: <code>{user[1] if user and user[1] else 'Not set'}</code>\n"
                    f"💬 Message: {msg_preview}\n"
                    f"📡 Status: {s}\n"
                    f"⏳ Runtime Today: {hours_used:.1f}h / 8h\n"
                    f"🔢 Max Groups: {FREE_MAX_GROUPS}",
                    back_keyboard())

            elif data == 'setmessage':
                self.pending_message[uid] = True
                edit_msg(uid, mid,
                    "💬 <b>Set Your Ad Message</b>\n\n"
                    "✍️ Send your promotional message now:\n\n"
                    "<i>Type /cancel to go back</i>",
                    make_keyboard([[{"text": "❌ Cancel",
                                     "callback_data": "dashboard"}]]))

            elif data == 'startcampaign':
                if not user or not user[4]:  # no session
                    await event.answer("❌ Login first!", alert=True)
                    return
                if not user[5]:  # no promo message
                    await event.answer("❌ Set your ad message first!", alert=True)
                    return
                if uid in self.tasks:
                    await event.answer("⚠️ Campaign already running!", alert=True)
                    return
                # Check runtime limit
                runtime = self.db.get_runtime_today(uid)
                if runtime >= FREE_MAX_RUNTIME:
                    edit_msg(uid, mid,
                        "⏰ <b>Daily Limit Reached!</b>\n\n"
                        "You've used your 8 hour free daily limit.\n\n"
                        "⏳ Come back tomorrow or upgrade to Premium\nfor unlimited runtime!",
                        upgrade_keyboard())
                    return
                self.db.set_campaign_status(uid, 1)
                self.campaign_start_times[uid] = datetime.now()
                task = asyncio.create_task(self.run_campaign(uid))
                self.tasks[uid] = task
                self.logger.send_log(uid, f"🆓 Free campaign started by {user[1]}")
                edit_msg(uid, mid, dashboard_text(self.db.get_user(uid), runtime),
                        dashboard_keyboard())
                send_msg(uid,
                    "🚀 <b>Free Campaign Started!</b>\n\n"
                    f"📊 Limit: {FREE_MAX_GROUPS} groups\n"
                    f"⏱️ Message delay: {FREE_MSG_DELAY}s\n"
                    f"🔄 Cycle delay: {FREE_CYCLE_DELAY//60}m\n"
                    f"⏳ Daily limit: 8 hours\n\n"
                    "💎 <i>Upgrade for unlimited access!</i>")

            elif data == 'stopcampaign':
                if uid not in self.tasks:
                    await event.answer("⚠️ No campaign running!", alert=True)
                    return
                self.db.set_campaign_status(uid, 0)
                self.tasks[uid].cancel()
                del self.tasks[uid]
                # Save runtime
                if uid in self.campaign_start_times:
                    elapsed = (datetime.now() -
                              self.campaign_start_times[uid]).total_seconds()
                    self.db.add_runtime(uid, int(elapsed))
                    del self.campaign_start_times[uid]
                self.logger.send_log(uid, "🛑 Free campaign stopped")
                edit_msg(uid, mid,
                        dashboard_text(self.db.get_user(uid),
                                      self.db.get_runtime_today(uid)),
                        dashboard_keyboard())
                send_msg(uid, "🛑 <b>Campaign Stopped!</b>")

            elif data == 'login':
                if user and user[4]:
                    await event.answer("✅ Already logged in!", alert=True)
                    return
                self.login_states[uid] = {'step': 'waiting_api'}
                edit_msg(uid, mid,
                    "🔑 <b>Login to Your Telegram Account</b>\n\n"
                    "<b>Step 1:</b> Get your API credentials\n"
                    "• Go to: https://my.telegram.org/apps\n"
                    "• Login and create an app\n"
                    "• Copy your API_ID and API_HASH\n\n"
                    "<b>Step 2:</b> Send them here:\n"
                    "<code>API_ID API_HASH</code>\n\n"
                    "Example: <code>12345678 abcdef1234567890</code>\n\n"
                    "<i>Type /cancel to go back</i>",
                    make_keyboard([[{"text": "❌ Cancel",
                                     "callback_data": "cancel_login"}]]))

            elif data == 'cancel_login':
                if uid in self.login_states:
                    try:
                        c = self.login_states[uid].get('client')
                        if c: await c.disconnect()
                    except: pass
                    del self.login_states[uid]
                edit_msg(uid, mid, dashboard_text(user, runtime), dashboard_keyboard())

            elif data == 'logout':
                if uid in self.tasks:
                    self.tasks[uid].cancel()
                    del self.tasks[uid]
                self.db.logout_user(uid)
                edit_msg(uid, mid,
                        dashboard_text(self.db.get_user(uid), 0),
                        dashboard_keyboard())
                send_msg(uid, "✅ <b>Logged out successfully!</b>")

        # ── GLOBAL MESSAGE HANDLER ───────────────

        @self.bot.on(events.NewMessage())
        async def global_handler(event):
            uid = event.sender_id
            text = event.message.text
            if not text: return

            if self.db.is_banned(uid):
                return

            if text.strip() == '/cancel':
                if uid in self.pending_message:
                    del self.pending_message[uid]
                if uid in self.login_states:
                    try:
                        c = self.login_states[uid].get('client')
                        if c: await c.disconnect()
                    except: pass
                    del self.login_states[uid]
                user = self.db.get_user(uid)
                runtime = self.db.get_runtime_today(uid) if user else 0
                send_msg(uid, dashboard_text(user, runtime), dashboard_keyboard())
                return

            # Pending setmessage
            if uid in self.pending_message and not text.startswith('/'):
                del self.pending_message[uid]
                self.db.set_promo_message(uid, text)
                send_msg(uid,
                    "✅ <b>Ad Message Saved!</b>\n\n"
                    f"📝 Preview:\n<i>{text[:100]}{'...' if len(text) > 100 else ''}</i>",
                    make_keyboard([
                        [{"text": "🚀 Start Campaign",
                          "callback_data": "startcampaign"}],
                        [{"text": "🏠 Dashboard", "callback_data": "dashboard"}]
                    ]))
                return

            # Login flow
            if uid in self.login_states:
                await self.handle_login(event, uid, text)

    async def handle_login(self, event, uid, text):
        if text.startswith('/'): return
        state = self.login_states[uid]
        step = state.get('step')

        if step == 'waiting_api':
            try:
                parts = text.strip().split()
                if len(parts) != 2:
                    send_msg(uid, "❌ Format: <code>API_ID API_HASH</code>")
                    return
                api_id = int(parts[0])
                api_hash = parts[1]
                state['api_id'] = api_id
                state['api_hash'] = api_hash
                state['step'] = 'waiting_phone'
                send_msg(uid,
                    "✅ <b>API credentials received!</b>\n\n"
                    "📱 Now send your phone number:\n"
                    "Example: <code>+911234567890</code>",
                    make_keyboard([[{"text": "❌ Cancel",
                                     "callback_data": "cancel_login"}]]))
            except ValueError:
                send_msg(uid, "❌ API_ID must be a number. Try again.")
                del self.login_states[uid]

        elif step == 'waiting_phone':
            if not text.startswith('+'):
                send_msg(uid, "❌ Must start with country code. Example: <code>+911234567890</code>")
                return
            try:
                user_client = TelegramClient(
                    StringSession(), state['api_id'], state['api_hash'])
                await user_client.connect()
                await user_client.send_code_request(text.strip())
                state['client'] = user_client
                state['phone'] = text.strip()
                state['step'] = 'waiting_code'
                send_msg(uid,
                    "📨 <b>Code sent!</b>\n\nEnter the verification code:",
                    make_keyboard([[{"text": "❌ Cancel",
                                     "callback_data": "cancel_login"}]]))
            except Exception as e:
                send_msg(uid, f"❌ Error: {e}\n\nTry again.")
                del self.login_states[uid]

        elif step == 'waiting_code':
            code = text.replace('-', '').replace(' ', '')
            if not code.isdigit():
                send_msg(uid, "❌ Enter only the numeric code")
                return
            try:
                await state['client'].sign_in(state['phone'], code)
                await self._complete_login(uid, state)
            except SessionPasswordNeededError:
                state['step'] = 'waiting_password'
                send_msg(uid,
                    "🔐 <b>2FA Enabled</b>\n\nSend your 2FA password:",
                    make_keyboard([[{"text": "❌ Cancel",
                                     "callback_data": "cancel_login"}]]))
            except Exception as e:
                send_msg(uid, f"❌ Invalid code: {e}\n\nTry again.")
                await state['client'].disconnect()
                del self.login_states[uid]

        elif step == 'waiting_password':
            try:
                await state['client'].sign_in(password=text)
                await self._complete_login(uid, state)
            except Exception as e:
                send_msg(uid, f"❌ 2FA failed: {e}\n\nTry again.")
                await state['client'].disconnect()
                del self.login_states[uid]

    async def _complete_login(self, uid, state):
        """Complete login, save session and set branding"""
        session = state['client'].session.save()
        phone = state['phone']
        self.db.save_session(uid, phone, state['api_id'],
                            state['api_hash'], session)
        await state['client'].disconnect()
        del self.login_states[uid]
        self.logger.send_log(uid, f"✅ Free user logged in: {phone}")

        # Set branding on account
        user = self.db.get_user(uid)
        send_msg(uid,
            "✅ <b>Login Successful!</b>\n\n"
            f"📱 Account: <code>{phone}</code>\n\n"
            "🏷️ Setting up required branding on your account...\n"
            "<i>This is required for free tier usage.</i>")

        branding_ok = await self.set_branding(uid, user)
        if branding_ok:
            send_msg(uid,
                "✅ <b>Account Setup Complete!</b>\n\n"
                f"🏷️ Branding added to your last name:\n"
                f"<code>{FREE_BRANDING_LASTNAME}</code>\n\n"
                "⚠️ <b>Do not remove this branding!</b>\n"
                f"Removing it 3 times will ban you from free tier.\n\n"
                "💎 Upgrade to Premium to remove branding requirement!",
                make_keyboard([
                    [{"text": "💬 Set Ad Message",
                      "callback_data": "setmessage"}],
                    [{"text": "🏠 Dashboard", "callback_data": "dashboard"}]
                ]))
        else:
            send_msg(uid,
                "✅ <b>Login Successful!</b>\n\n"
                "⚠️ Could not set branding automatically.\n"
                f"Please manually add to your last name:\n"
                f"<code>{FREE_BRANDING_LASTNAME}</code>",
                make_keyboard([[{"text": "🏠 Dashboard",
                                  "callback_data": "dashboard"}]]))

    async def run_campaign(self, uid):
        """Run free campaign with all limits enforced"""
        try:
            user = self.db.get_user(uid)
            phone = user[1]
            session_string = user[4]
            message = user[5]

            user_client = TelegramClient(
                StringSession(session_string), user[2], user[3])
            await user_client.connect()

            dialogs = await user_client.get_dialogs()
            groups = [d for d in dialogs if d.is_group]

            # Enforce 100 group limit
            if len(groups) > FREE_MAX_GROUPS:
                groups = groups[:FREE_MAX_GROUPS]

            if not groups:
                send_msg(uid, "❌ <b>No groups found!</b>")
                self.db.set_campaign_status(uid, 0)
                await user_client.disconnect()
                return

            send_msg(uid,
                f"📊 <b>Free Campaign Ready!</b>\n\n"
                f"✅ Found <b>{len(groups)}</b> groups "
                f"(max {FREE_MAX_GROUPS})\n"
                f"⏱️ Delay: <b>{FREE_MSG_DELAY}s</b>\n"
                f"🔄 Cycle: <b>{FREE_CYCLE_DELAY//60}m</b>\n\n"
                f"🚀 Sending started...")

            round_num = 0
            campaign_start = datetime.now()

            while self.db.get_user(uid)[5]:
                # Check 8 hour limit
                runtime = self.db.get_runtime_today(uid)
                elapsed_this_session = (
                    datetime.now() - campaign_start).total_seconds()
                total_today = runtime + elapsed_this_session

                if total_today >= FREE_MAX_RUNTIME:
                    # Stop campaign - limit reached
                    self.db.set_campaign_status(uid, 0)
                    self.db.add_runtime(uid, int(elapsed_this_session))
                    if uid in self.campaign_start_times:
                        del self.campaign_start_times[uid]
                    send_msg(uid,
                        "⏰ <b>Daily Limit Reached!</b>\n\n"
                        "You've used your 8 hour free daily limit.\n\n"
                        "⏳ Your campaign will resume tomorrow automatically.\n\n"
                        "💎 Upgrade to Premium for unlimited runtime!",
                        upgrade_keyboard())
                    self.logger.send_log(uid, f"⏰ Free limit reached for {phone}")
                    break

                round_num += 1
                sent = 0
                failed = 0

                # Refresh message
                user = self.db.get_user(uid)
                message = user[5]

                for group in groups:
                    if not self.db.get_user(uid)[5]: break

                    # Re-check limit during sending
                    elapsed = (datetime.now() - campaign_start).total_seconds()
                    if runtime + elapsed >= FREE_MAX_RUNTIME:
                        break

                    try:
                        await user_client.send_message(group.entity, message)
                        sent += 1
                        self.logger.send_log(uid, f"✓ [{phone}] → {group.name}")
                        await asyncio.sleep(FREE_MSG_DELAY)
                    except FloodWaitError as e:
                        send_msg(uid, f"⚠️ <b>FloodWait!</b> Pausing {e.seconds}s...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        failed += 1
                        await asyncio.sleep(10)

                # Round summary
                hours_left = max(0, 8 - (runtime + elapsed_this_session) / 3600)
                send_msg(uid,
                    f"📊 <b>Round {round_num} Complete!</b>\n\n"
                    f"✅ Sent: <b>{sent}</b>\n"
                    f"❌ Failed: <b>{failed}</b>\n"
                    f"⏳ Runtime left today: <b>{hours_left:.1f}h</b>\n\n"
                    f"⏳ Next round in <b>{FREE_CYCLE_DELAY//60} minutes...</b>\n\n"
                    f"💎 <i>Upgrade for unlimited runtime!</i>",
                    make_keyboard([
                        [{"text": "🛑 Stop", "callback_data": "stopcampaign"}],
                        [{"text": "💎 Upgrade", "callback_data": "upgrade"}]
                    ]))

                await asyncio.sleep(FREE_CYCLE_DELAY)

            await user_client.disconnect()

        except asyncio.CancelledError:
            print(f"[{uid}] Free campaign cancelled")
            # Save runtime on cancel
            if uid in self.campaign_start_times:
                elapsed = (datetime.now() -
                          self.campaign_start_times[uid]).total_seconds()
                self.db.add_runtime(uid, int(elapsed))
                del self.campaign_start_times[uid]
        except Exception as e:
            print(f"[{uid}] Free campaign error: {e}")
            self.db.set_campaign_status(uid, 0)
            if uid in self.tasks: del self.tasks[uid]
            try:
                send_msg(uid, f"❌ <b>Campaign stopped due to error:</b>\n<code>{e}</code>")
            except: pass

# ============================================
# MAIN
# ============================================
async def main():
    print("=" * 50)
    print("  🆓 UZERON ADSBOT — Free Tier")
    print("=" * 50)
    missing = [v for v in ['API_ID', 'API_HASH', 'FREE_BOT_TOKEN',
                            'LOGGER_BOT_TOKEN', 'ADMIN_IDS', 'DATABASE_URL']
               if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        sys.exit(1)
    print("✓ All credentials loaded")
    await UzeronFreeBot().start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🆓 Free bot stopped")
    except Exception as e:
        print(f"Fatal: {e}")
        sys.exit(1)
