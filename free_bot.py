# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import psycopg2
import json
import pytz
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.account import UpdateProfileRequest
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL     = os.getenv('DATABASE_URL')
BOT_API_ID       = int(os.getenv('API_ID'))
BOT_API_HASH     = os.getenv('API_HASH')
FREE_BOT_TOKEN   = os.getenv('FREE_BOT_TOKEN')
LOGGER_BOT_TOKEN = os.getenv('LOGGER_BOT_TOKEN')
ADMINS           = [int(x.strip()) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip()]

CHANNEL_LINK      = "https://t.me/Uzeron_AdsBot"
COMMUNITY_LINK    = "https://t.me/UzeronCommunity"
HOW_TO_USE_LINK   = "https://t.me/Uzeron_Ads"
SUPPORT_LINK      = "https://t.me/Uzeron_Ads_support"
CONTACT_USERNAME  = "@Pandaysubscription"
PREMIUM_BOT       = "@Uzeron_AdsBot"

CHANNEL_USERNAME   = "Uzeron_AdsBot"
COMMUNITY_USERNAME = "UzeronCommunity"

IST = pytz.timezone('Asia/Kolkata')

FREE_MAX_GROUPS          = 100
FREE_CYCLE_DELAY         = 600
FREE_MSG_DELAY           = 60
FREE_MAX_RUNTIME         = 8 * 3600
FREE_BRANDING_TAG        = "• via @Uzeron_AdsBot"
FREE_BRANDING_LASTNAME   = FREE_BRANDING_TAG
FREE_BRANDING_BIO        = "Free Automated ads • via @Uzeron_AdsBot"
FREE_WARNINGS_BEFORE_BAN = 3

# ═══════════════════════════════════════════════════════════════════════════
# BOT API HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _bot(method, data=None, token=None):
    t   = token or FREE_BOT_TOKEN
    url = f"https://api.telegram.org/bot{t}/{method}"
    try:
        processed = {k: json.dumps(v) if isinstance(v, (dict, list)) else v
                     for k, v in (data or {}).items()}
        r = requests.post(url, data=processed, timeout=10)
        return r.json()
    except Exception as e:
        print(f"Bot API [{method}]: {e}")
        return {}

def send_msg(chat_id, text, keyboard=None):
    d = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard: d["reply_markup"] = json.dumps(keyboard)
    return _bot("sendMessage", d)

def edit_msg(chat_id, msg_id, text, keyboard=None):
    d = {"chat_id": chat_id, "message_id": msg_id,
         "text": text, "parse_mode": "HTML"}
    if keyboard: d["reply_markup"] = json.dumps(keyboard)
    _bot("editMessageText", d)

def kb(buttons):
    return {"inline_keyboard": buttons}

# ── Send log to user via LOGGER bot ────────────────────────────────────────
def user_log(user_id, text):
    """Send a log message to the user via the LOGGER bot token.
    User must have started the logger bot first (/start on it).
    Errors are silently ignored — logging should never break the main flow."""
    try:
        _bot("sendMessage", {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        }, token=LOGGER_BOT_TOKEN)
    except Exception as e:
        print(f"user_log uid={user_id}: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# MEMBERSHIP CHECK
# ═══════════════════════════════════════════════════════════════════════════
def check_member(user_id, chat_username):
    r = _bot("getChatMember", {
        "chat_id": f"@{chat_username}",
        "user_id": user_id
    })
    print(f"getChatMember @{chat_username} uid={user_id}: {r}")
    if not r.get("ok"):
        err = r.get("description", "unknown error")
        return False, err
    status = r.get("result", {}).get("status", "left")
    is_member = status in ("member", "administrator", "creator", "restricted")
    return is_member, None

def user_has_joined(user_id):
    ch_ok,  ch_err  = check_member(user_id, CHANNEL_USERNAME)
    com_ok, com_err = check_member(user_id, COMMUNITY_USERNAME)
    return ch_ok, com_ok, ch_err, com_err

# ═══════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════
def force_join_keyboard():
    return kb([
        [{"text": "📢 Join Updates Channel", "url": CHANNEL_LINK}],
        [{"text": "👥 Join Community",        "url": COMMUNITY_LINK}],
        [{"text": "✅ I've Joined — Continue","callback_data": "check_join"}],
    ])

def welcome_keyboard():
    return kb([
        [{"text": "🚀 Open Dashboard",        "callback_data": "dashboard"}],
        [{"text": "📢 Updates",  "url": CHANNEL_LINK},
         {"text": "🆘 Support",  "url": SUPPORT_LINK}],
        [{"text": "📖 How To Use", "url": HOW_TO_USE_LINK}],
        [{"text": "💎 Go Premium", "callback_data": "upgrade"}],
    ])

def dashboard_keyboard():
    return kb([
        [{"text": "👤 My Account",     "callback_data": "account"},
         {"text": "📊 Status",         "callback_data": "status"}],
        [{"text": "💬 Set Message",    "callback_data": "setmessage"},
         {"text": "⏱️ 60s | 10m",     "callback_data": "delay_info"}],
        [{"text": "🚀 Start Campaign", "callback_data": "startcampaign"},
         {"text": "🛑 Stop Campaign",  "callback_data": "stopcampaign"}],
        [{"text": "🔑 Login",          "callback_data": "login"},
         {"text": "💎 Upgrade",        "callback_data": "upgrade"}],
        [{"text": "📢 Updates",        "url": CHANNEL_LINK},
         {"text": "📖 How To Use",     "url": HOW_TO_USE_LINK}],
        [{"text": "🚪 Logout",         "callback_data": "logout"}],
    ])

def upgrade_keyboard():
    return kb([
        [{"text": f"💎 Upgrade → {CONTACT_USERNAME}", "url": "https://t.me/Pandaysubscription"}],
        [{"text": "📢 Updates", "url": CHANNEL_LINK},
         {"text": "🆘 Support", "url": SUPPORT_LINK}],
        [{"text": "🔙 Back", "callback_data": "dashboard"}],
    ])

def back_keyboard():
    return kb([[{"text": "🏠 Dashboard", "callback_data": "dashboard"}]])

def numpad_keyboard(prefix, entered=""):
    display = entered or "—"
    rows = [
        [{"text": f"📟  {display}  ", "callback_data": f"{prefix}_display"}],
        [{"text":"1","callback_data":f"{prefix}_1"},
         {"text":"2","callback_data":f"{prefix}_2"},
         {"text":"3","callback_data":f"{prefix}_3"}],
        [{"text":"4","callback_data":f"{prefix}_4"},
         {"text":"5","callback_data":f"{prefix}_5"},
         {"text":"6","callback_data":f"{prefix}_6"}],
        [{"text":"7","callback_data":f"{prefix}_7"},
         {"text":"8","callback_data":f"{prefix}_8"},
         {"text":"9","callback_data":f"{prefix}_9"}],
        [{"text":"⌫ Del",     "callback_data":f"{prefix}_del"},
         {"text":"0",         "callback_data":f"{prefix}_0"},
         {"text":"✅ Submit", "callback_data":f"{prefix}_submit"}],
        [{"text":"❌ Cancel Login","callback_data":"cancel_login"}],
    ]
    return kb(rows)

# ═══════════════════════════════════════════════════════════════════════════
# TEXTS
# ═══════════════════════════════════════════════════════════════════════════
def force_join_text(missing=None):
    base = (
        "👋 <b>Welcome to Uzeron AdsBot!</b>\n\n"
        "To unlock the bot, please join both:\n\n"
        "📢 <b>Updates Channel</b> — latest news & updates\n"
        "👥 <b>Community Group</b> — support & discussion\n\n"
        "<i>After joining both, tap the button below.</i>"
    )
    if missing:
        base += "\n\n❌ <b>Still not joined:</b>\n" + "\n".join(f"• {m}" for m in missing)
    return base

def welcome_text():
    return (
        "⚡ <b>Welcome to Uzeron AdsBot — Free Plan</b>\n\n"
        "╔══════════════════════╗\n"
        "║  📢 100 Groups Max\n"
        "║  ⏱️ 60s Message Delay\n"
        "║  🔄 10min Cycle Delay\n"
        "║  ⏳ 8 Hours Daily Runtime\n"
        "║  🏷️ Account Branding Required\n"
        "╚══════════════════════╝\n\n"
        "💎 <b>Upgrade to Premium for:</b>\n"
        "• Unlimited groups & runtime\n"
        "• Custom delays • No branding\n"
        "• Message rotation & auto schedule\n\n"
        f"👥 Community: {COMMUNITY_LINK}\n"
        f"🆘 Support: {SUPPORT_LINK}"
    )

def dashboard_text(user, runtime):
    phone   = user[1] if user and user[1] else "Not connected"
    msg_st  = "✅ Set"   if user and user[5] else "❌ Not set"
    camp_st = "🟢 Live"  if user and user[6] else "🔴 Stopped"
    hu = runtime / 3600
    hl = max(0, 8 - hu)
    return (
        "⚡ <b>UZERON ADSBOT — Free Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Account:</b> <code>{phone}</code>\n"
        f"💬 <b>Ad Message:</b> {msg_st}\n"
        f"⏱️ <b>Delay:</b> 60s  |  <b>Cycle:</b> 10m\n"
        f"⏳ <b>Runtime Today:</b> {hu:.1f}h / 8h\n"
        f"🕐 <b>Time Left:</b> {hl:.1f}h\n"
        f"📡 <b>Campaign:</b> {camp_st}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Free plan: 100 groups, 8hr/day limit</i>"
    )

def upgrade_text():
    return (
        "💎 <b>UPGRADE TO PREMIUM</b>\n\n"
        "╔══════════════════════╗\n"
        "║  🚀 Unlimited Groups\n"
        "║  ⏱️ Custom Delays\n"
        "║  🔀 Message Rotation\n"
        "║  ⏰ Auto Schedule\n"
        "║  🏷️ No Branding\n"
        "║  24/7 Priority Support\n"
        "╚══════════════════════╝\n\n"
        f"👤 Contact: <b>{CONTACT_USERNAME}</b>\n"
        f"🤖 Premium Bot: <b>{PREMIUM_BOT}</b>"
    )

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════
class Database:
    def get_conn(self):
        return psycopg2.connect(DATABASE_URL, sslmode='require')

    def init_db(self):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS free_users (
            user_id        BIGINT PRIMARY KEY,
            username       TEXT,
            phone          TEXT,
            api_id         INTEGER,
            api_hash       TEXT,
            session_string TEXT,
            promo_message  TEXT,
            is_active      INTEGER DEFAULT 0,
            runtime_today  INTEGER DEFAULT 0,
            last_reset     TEXT,
            warning_count  INTEGER DEFAULT 0,
            is_banned      INTEGER DEFAULT 0,
            branding_set   INTEGER DEFAULT 0,
            created_at     TEXT
        )''')
        conn.commit(); conn.close()

    def get_user(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('''SELECT user_id,phone,api_id,api_hash,session_string,
                     promo_message,is_active,runtime_today,last_reset,
                     warning_count,is_banned,branding_set
                     FROM free_users WHERE user_id=%s''', (user_id,))
        r = c.fetchone(); conn.close(); return r

    def register_user(self, user_id, username):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT user_id FROM free_users WHERE user_id=%s',(user_id,))
        if not c.fetchone():
            c.execute('INSERT INTO free_users(user_id,username,created_at) VALUES(%s,%s,%s)',
                      (user_id, username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
        conn.close()

    def is_banned(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT is_banned FROM free_users WHERE user_id=%s',(user_id,))
        r = c.fetchone(); conn.close()
        return r and r[0] == 1

    def save_session(self, user_id, phone, api_id, api_hash, session_string):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET phone=%s,api_id=%s,api_hash=%s,session_string=%s WHERE user_id=%s',
                  (phone, api_id, api_hash, session_string, user_id))
        conn.commit(); conn.close()

    def set_promo_message(self, user_id, msg):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET promo_message=%s WHERE user_id=%s',(msg,user_id))
        conn.commit(); conn.close()

    def set_campaign_status(self, user_id, status):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET is_active=%s WHERE user_id=%s',(status,user_id))
        conn.commit(); conn.close()

    def get_runtime_today(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT runtime_today,last_reset FROM free_users WHERE user_id=%s',(user_id,))
        r = c.fetchone(); conn.close()
        if not r: return 0
        runtime, last_reset = r
        today = datetime.now(IST).strftime('%Y-%m-%d')
        if last_reset != today:
            self._reset_runtime(user_id, today); return 0
        return runtime or 0

    def _reset_runtime(self, user_id, today):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET runtime_today=0,last_reset=%s WHERE user_id=%s',(today,user_id))
        conn.commit(); conn.close()

    def add_runtime(self, user_id, seconds):
        conn = self.get_conn(); c = conn.cursor()
        today = datetime.now(IST).strftime('%Y-%m-%d')
        c.execute('UPDATE free_users SET runtime_today=COALESCE(runtime_today,0)+%s,last_reset=%s WHERE user_id=%s',
                  (seconds,today,user_id))
        conn.commit(); conn.close()

    def set_branding(self, user_id, status):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET branding_set=%s WHERE user_id=%s',(status,user_id))
        conn.commit(); conn.close()

    def add_warning(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET warning_count=COALESCE(warning_count,0)+1 WHERE user_id=%s',(user_id,))
        c.execute('SELECT warning_count FROM free_users WHERE user_id=%s',(user_id,))
        count = c.fetchone()[0]
        if count >= FREE_WARNINGS_BEFORE_BAN:
            c.execute('UPDATE free_users SET is_banned=1 WHERE user_id=%s',(user_id,))
        conn.commit(); conn.close(); return count

    def ban_user(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('UPDATE free_users SET is_banned=1 WHERE user_id=%s',(user_id,))
        conn.commit(); conn.close()

    def logout_user(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('''UPDATE free_users SET phone=NULL,api_id=NULL,api_hash=NULL,
                     session_string=NULL,is_active=0,branding_set=0 WHERE user_id=%s''',(user_id,))
        conn.commit(); conn.close()

    def get_all_active_with_branding(self):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT user_id,username FROM free_users WHERE is_banned=0 AND branding_set=1')
        r = c.fetchall(); conn.close(); return r

    def get_all_users(self):
        conn = self.get_conn(); c = conn.cursor()
        c.execute('SELECT user_id,username FROM free_users WHERE is_banned=0')
        r = c.fetchall(); conn.close(); return r

# ═══════════════════════════════════════════════════════════════════════════
# LOGGER
# ═══════════════════════════════════════════════════════════════════════════
class Logger:
    def __init__(self, token): self.token = token
    def log(self, chat_id, text):
        try:
            _bot("sendMessage",{"chat_id":chat_id,"text":text,"parse_mode":"HTML"},token=self.token)
        except: pass

# ═══════════════════════════════════════════════════════════════════════════
# MAIN BOT CLASS
# ═══════════════════════════════════════════════════════════════════════════
class UzeronFreeBot:
    def __init__(self):
        bot_session           = os.getenv('BOT_SESSION_STRING', '')
        self.bot              = TelegramClient(StringSession(bot_session), BOT_API_ID, BOT_API_HASH)
        self.db               = Database()
        self.db.init_db()
        self.logger           = Logger(LOGGER_BOT_TOKEN)
        self.tasks            = {}
        self.campaign_start_times = {}
        self.pending_message      = {}
        self.login_states         = {}
        self.broadcast_state      = {}
        self._join_cache          = {}

    async def start(self):
        await self.bot.start(bot_token=FREE_BOT_TOKEN)
        session_str = self.bot.session.save()
        if not os.getenv('BOT_SESSION_STRING'):
            print("="*60)
            print("Add to Railway env → BOT_SESSION_STRING:")
            print(session_str)
            print("="*60)
        self.register_handlers()
        asyncio.create_task(self.branding_checker())
        print("✓ Uzeron Free Bot live!")
        await self.bot.run_until_disconnected()

    # ─── FORCE-JOIN ───────────────────────────────────────────────────────
    def _check_join(self, uid):
        if uid in ADMINS:
            return True, [], False
        if self._join_cache.get(uid):
            return True, [], False
        missing = []
        has_api_error = False
        ch_ok, ch_err   = check_member(uid, CHANNEL_USERNAME)
        com_ok, com_err = check_member(uid, COMMUNITY_USERNAME)
        if ch_err and com_err:
            print(f"WARNING: Both membership checks failed uid={uid}. Failing open.")
            self._join_cache[uid] = True
            return True, [], True
        if not ch_ok:
            if ch_err: print(f"WARNING: Channel check error uid={uid}: {ch_err!r} — skipping")
            else: missing.append("📢 Updates Channel")
        if not com_ok:
            if com_err: print(f"WARNING: Community check error uid={uid}: {com_err!r} — skipping")
            else: missing.append("👥 Community Group")
        all_joined = len(missing) == 0
        if all_joined:
            self._join_cache[uid] = True
        return all_joined, missing, has_api_error

    # ─── BRANDING ─────────────────────────────────────────────────────────
    async def apply_branding_on_live_client(self, uid, live_client):
        try:
            me       = await live_client.get_me()
            cur_last = (me.last_name or "").strip()
            if FREE_BRANDING_TAG in cur_last:
                cur_last = cur_last.replace(FREE_BRANDING_TAG, "").strip()
            new_last = f"{cur_last} {FREE_BRANDING_TAG}".strip() if cur_last else FREE_BRANDING_TAG
            print(f"Branding uid={uid}: '{me.last_name}' → '{new_last}'")
            await live_client(UpdateProfileRequest(last_name=new_last, about=FREE_BRANDING_BIO))
            self.db.set_branding(uid, 1)
            print(f"✅ Branding OK uid={uid}")
            return True
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"apply_branding uid={uid} ERROR: {err}")
            try:
                if ADMINS: self.logger.log(ADMINS[0], f"⚠️ Branding failed uid={uid}\n<code>{err}</code>")
            except: pass
            return False

    async def set_branding(self, uid, session_str, api_id, api_hash):
        c = None
        try:
            c = TelegramClient(StringSession(session_str), api_id, api_hash)
            await c.connect()
            if not await c.is_user_authorized():
                await c.disconnect(); return False
            ok = await self.apply_branding_on_live_client(uid, c)
            await c.disconnect(); return ok
        except Exception as e:
            print(f"set_branding uid={uid}: {e}")
            try:
                if c: await c.disconnect()
            except: pass
            return False

    async def branding_checker(self):
        while True:
            await asyncio.sleep(1800)
            for uid, _ in self.db.get_all_active_with_branding():
                user = self.db.get_user(uid)
                if user and user[4]:
                    asyncio.create_task(self._verify_branding(uid, user))

    async def _verify_branding(self, uid, user):
        try:
            c = TelegramClient(StringSession(user[4]), user[2], user[3])
            await c.connect()
            if not await c.is_user_authorized():
                await c.disconnect(); return
            me = await c.get_me()
            await c.disconnect()
            if FREE_BRANDING_TAG not in (me.last_name or ""):
                count = self.db.add_warning(uid)
                left  = FREE_WARNINGS_BEFORE_BAN - count
                if count >= FREE_WARNINGS_BEFORE_BAN:
                    if uid in self.tasks: self.tasks[uid].cancel(); del self.tasks[uid]
                    self.db.set_campaign_status(uid, 0)
                    send_msg(uid, "🚫 <b>Banned!</b> Branding removed 3× — upgrade to continue.", upgrade_keyboard())
                    user_log(uid, "🚫 <b>Account banned</b> — branding removed 3 times.")
                else:
                    u = self.db.get_user(uid)
                    await self.set_branding(uid, u[4], u[2], u[3])
                    send_msg(uid,
                        f"⚠️ <b>Warning {count}/3</b> — branding removed & re-applied.\n"
                        f"{left} warning(s) left before ban.", upgrade_keyboard())
                    user_log(uid, f"⚠️ Branding warning {count}/3 — re-applied automatically.")
        except Exception as e:
            print(f"verify_branding uid={uid}: {e}")

    # ─── BROADCAST ────────────────────────────────────────────────────────
    async def do_broadcast(self, admin_uid, message_text):
        users   = self.db.get_all_users()
        total   = len(users)
        success = 0; failed = 0
        send_msg(admin_uid, f"📣 Broadcasting to <b>{total}</b> users…")
        for uid, _ in users:
            try:
                send_msg(uid, message_text)
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        send_msg(admin_uid,
            f"✅ <b>Broadcast done!</b>\n\n👥 Total: {total}\n✅ Sent: {success}\n❌ Failed: {failed}")

    # ─── HANDLERS ─────────────────────────────────────────────────────────
    def register_handlers(self):

        @self.bot.on(events.NewMessage(pattern='/users'))
        async def h_users(event):
            if event.sender_id not in ADMINS: return
            ul  = self.db.get_all_users()
            msg = f"👥 <b>Free Users ({len(ul)}):</b>\n\n" + \
                  "".join(f"• {'@'+u if u else str(i)}\n" for i,u in ul)
            await event.reply(msg or "No users.", parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/ban'))
        async def h_ban(event):
            if event.sender_id not in ADMINS: return
            try:
                uid = int(event.message.text.split()[1])
                self.db.ban_user(uid)
                if uid in self.tasks: self.tasks[uid].cancel(); del self.tasks[uid]
                await event.reply(f"✅ Banned {uid}")
                send_msg(uid, f"🚫 Banned. Contact {CONTACT_USERNAME}", upgrade_keyboard())
                user_log(uid, f"🚫 Your account has been banned by admin.")
            except: await event.reply("❌ Usage: /ban USER_ID")

        @self.bot.on(events.NewMessage(pattern='/stats'))
        async def h_stats(event):
            if event.sender_id not in ADMINS: return
            await event.reply(
                f"📊 <b>Stats</b>\n\n👥 Users: {len(self.db.get_all_users())}\n🚀 Running: {len(self.tasks)}",
                parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/broadcast'))
        async def h_broadcast(event):
            if event.sender_id not in ADMINS: return
            uid = event.sender_id
            self.broadcast_state[uid] = {'step': 'waiting_msg'}
            await event.reply(
                "📣 <b>Broadcast</b>\n\nSend the message to broadcast to all users.\n<i>/cancel to abort</i>",
                parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/checkjoin'))
        async def h_checkjoin(event):
            if event.sender_id not in ADMINS: return
            uid = event.sender_id
            ch_ok, ch_err  = check_member(uid, CHANNEL_USERNAME)
            com_ok, com_err = check_member(uid, COMMUNITY_USERNAME)
            await event.reply(
                f"🔍 <b>Membership Check Debug</b>\n\n"
                f"Your UID: <code>{uid}</code>\n\n"
                f"📢 Channel (@{CHANNEL_USERNAME}):\n"
                f"  Result: {'✅ Member' if ch_ok else '❌ Not member'}\n"
                f"  Error: <code>{ch_err or 'None'}</code>\n\n"
                f"👥 Community (@{COMMUNITY_USERNAME}):\n"
                f"  Result: {'✅ Member' if com_ok else '❌ Not member'}\n"
                f"  Error: <code>{com_err or 'None'}</code>",
                parse_mode='html')

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def h_start(event):
            uid = event.sender_id
            if self.db.is_banned(uid):
                send_msg(uid, "🚫 You are banned.", upgrade_keyboard()); return
            self.db.register_user(uid, event.sender.username)
            all_joined, missing, api_error = self._check_join(uid)
            if not all_joined:
                send_msg(uid, force_join_text(missing), force_join_keyboard()); return
            send_msg(uid, welcome_text(), welcome_keyboard())

        @self.bot.on(events.CallbackQuery())
        async def h_cb(event):
            uid  = event.sender_id
            data = event.data.decode()
            mid  = event.query.msg_id

            if self.db.is_banned(uid):
                await event.answer("🚫 Banned!", alert=True); return

            user    = self.db.get_user(uid)
            runtime = self.db.get_runtime_today(uid) if user else 0

            if data == 'check_join':
                await event.answer()
                self._join_cache.pop(uid, None)
                all_joined, missing, api_error = self._check_join(uid)
                if all_joined:
                    edit_msg(uid, mid, welcome_text(), welcome_keyboard())
                else:
                    edit_msg(uid, mid, force_join_text(missing), force_join_keyboard())
                return

            all_joined, missing, api_error = self._check_join(uid)
            if not all_joined:
                await event.answer("❌ Join channel & community first!", alert=True)
                edit_msg(uid, mid, force_join_text(missing), force_join_keyboard())
                return

            if data == 'dashboard':
                await event.answer()
                edit_msg(uid, mid, dashboard_text(user, runtime), dashboard_keyboard()); return

            if data == 'upgrade':
                await event.answer()
                edit_msg(uid, mid, upgrade_text(), upgrade_keyboard()); return

            if data == 'delay_info':
                await event.answer("60s message delay | 10min cycle.\nUpgrade for custom!", alert=True); return

            if data == 'account':
                await event.answer()
                ph  = user[1] if user and user[1] else "Not connected"
                con = "✅ Connected" if user and user[4] else "❌ Not connected"
                brd = "✅ Set" if user and user[11] else "⏳ Pending"
                edit_msg(uid, mid,
                    f"👤 <b>My Account</b>\n\n"
                    f"📱 Phone: <code>{ph}</code>\n"
                    f"🔗 Status: {con}\n"
                    f"🏷️ Branding: {brd}",
                    kb([[{"text":"🔑 Login","callback_data":"login"},
                         {"text":"🚪 Logout","callback_data":"logout"}],
                        [{"text":"🏠 Dashboard","callback_data":"dashboard"}]])); return

            if data == 'status':
                await event.answer()
                s  = "🟢 Live" if user and user[6] else "🔴 Stopped"
                mp = ((user[5][:60]+'…') if user and user[5] and len(user[5])>60
                      else (user[5] if user else "Not set") or "Not set")
                edit_msg(uid, mid,
                    f"📊 <b>Status</b>\n\n"
                    f"📱 <code>{user[1] if user and user[1] else 'Not set'}</code>\n"
                    f"💬 {mp}\n📡 {s}\n⏳ {runtime/3600:.1f}h / 8h",
                    back_keyboard()); return

            if data == 'setmessage':
                await event.answer()
                self.pending_message[uid] = True
                edit_msg(uid, mid,
                    "💬 <b>Set Your Ad Message</b>\n\n✍️ Send your promotional message now:\n<i>/cancel to go back</i>",
                    kb([[{"text":"❌ Cancel","callback_data":"dashboard"}]])); return

            if data == 'logout':
                await event.answer()
                if uid in self.tasks: self.tasks[uid].cancel(); del self.tasks[uid]
                phone = user[1] if user and user[1] else "unknown"
                self.db.logout_user(uid)
                edit_msg(uid, mid, dashboard_text(self.db.get_user(uid), 0), dashboard_keyboard())
                send_msg(uid, "✅ Logged out successfully!")
                user_log(uid,
                    f"🚪 <b>Account logged out</b>\n"
                    f"📱 Phone: <code>{phone}</code>\n"
                    f"🕐 Time: {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}")
                return

            if data == 'startcampaign':
                await event.answer()
                if not user or not user[4]:
                    send_msg(uid, "❌ Please login first!"); return
                if not user[5]:
                    send_msg(uid, "❌ Set your ad message first!"); return
                if uid in self.tasks:
                    send_msg(uid, "⚠️ Campaign already running!"); return
                if runtime >= FREE_MAX_RUNTIME:
                    edit_msg(uid, mid, "⏰ <b>Daily Limit Reached!</b>\n\nCome back tomorrow or upgrade.", upgrade_keyboard()); return
                self.db.set_campaign_status(uid, 1)
                self.campaign_start_times[uid] = datetime.now()
                self.tasks[uid] = asyncio.create_task(self.run_campaign(uid))
                edit_msg(uid, mid, dashboard_text(self.db.get_user(uid), runtime), dashboard_keyboard())
                send_msg(uid,
                    f"🚀 <b>Campaign Started!</b>\n\n"
                    f"📊 {FREE_MAX_GROUPS} groups  |  ⏱️ {FREE_MSG_DELAY}s  |  "
                    f"🔄 {FREE_CYCLE_DELAY//60}m cycle  |  ⏳ 8h daily")
                user_log(uid,
                    f"🚀 <b>Campaign Started</b>\n"
                    f"📱 Account: <code>{user[1]}</code>\n"
                    f"🕐 Time: {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}")
                return

            if data == 'stopcampaign':
                await event.answer()
                if uid not in self.tasks:
                    send_msg(uid, "⚠️ No campaign running!"); return
                self.db.set_campaign_status(uid, 0)
                self.tasks[uid].cancel(); del self.tasks[uid]
                elapsed = 0
                if uid in self.campaign_start_times:
                    elapsed = (datetime.now()-self.campaign_start_times[uid]).total_seconds()
                    self.db.add_runtime(uid, int(elapsed)); del self.campaign_start_times[uid]
                edit_msg(uid, mid,
                    dashboard_text(self.db.get_user(uid), self.db.get_runtime_today(uid)),
                    dashboard_keyboard())
                send_msg(uid, "🛑 <b>Campaign Stopped!</b>")
                user_log(uid,
                    f"🛑 <b>Campaign Stopped</b>\n"
                    f"📱 Account: <code>{user[1] if user and user[1] else 'N/A'}</code>\n"
                    f"⏱️ Session runtime: {elapsed/3600:.1f}h\n"
                    f"🕐 Time: {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}")
                return

            if data == 'login':
                await event.answer()
                if user and user[4]:
                    send_msg(uid, "✅ Already logged in!"); return
                self.login_states[uid] = {'step': 'api'}
                edit_msg(uid, mid,
                    "🔑 <b>Login — Step 1/3: API Credentials</b>\n\n"
                    "Send your credentials in <b>one message</b>:\n"
                    "<code>API_ID API_HASH</code>\n\n"
                    "📌 Get from: <a href='https://my.telegram.org/apps'>my.telegram.org/apps</a>\n"
                    "Example: <code>12345678 abc123def456</code>\n\n"
                    "<i>/cancel to go back</i>",
                    kb([[{"text":"❌ Cancel","callback_data":"cancel_login"}]])); return

            if data == 'cancel_login':
                await event.answer()
                await self._cleanup_login(uid)
                edit_msg(uid, mid, dashboard_text(user, runtime), dashboard_keyboard()); return

            if data.startswith('otp_'):
                await self._handle_numpad(event, uid, mid, data, 'otp'); return

        @self.bot.on(events.NewMessage())
        async def h_text(event):
            uid  = event.sender_id
            text = (event.message.text or '').strip()
            if not text or self.db.is_banned(uid): return

            if text == '/cancel':
                await self._cleanup_login(uid)
                if uid in self.pending_message: del self.pending_message[uid]
                if uid in self.broadcast_state: del self.broadcast_state[uid]
                user    = self.db.get_user(uid)
                runtime = self.db.get_runtime_today(uid) if user else 0
                send_msg(uid, dashboard_text(user, runtime), dashboard_keyboard()); return

            if uid in self.broadcast_state and uid in ADMINS:
                if not text.startswith('/'):
                    del self.broadcast_state[uid]
                    asyncio.create_task(self.do_broadcast(uid, text)); return

            if uid in self.pending_message and not text.startswith('/'):
                del self.pending_message[uid]
                self.db.set_promo_message(uid, text)
                send_msg(uid,
                    f"✅ <b>Ad Message Saved!</b>\n\n📝 <i>{text[:100]}{'…' if len(text)>100 else ''}</i>",
                    kb([[{"text":"🚀 Start Campaign","callback_data":"startcampaign"}],
                        [{"text":"🏠 Dashboard","callback_data":"dashboard"}]])); return

            if uid in self.login_states:
                state = self.login_states[uid]
                if not text.startswith('/'):
                    if state['step'] == 'api':
                        await self._login_got_api(uid, text)
                    elif state['step'] == 'phone':
                        await self._login_got_phone(uid, text)
                    elif state['step'] == '2fa':
                        await self._login_got_2fa(uid, text)

    # ─── LOGIN HELPERS ─────────────────────────────────────────────────────
    async def _cleanup_login(self, uid):
        if uid in self.login_states:
            try:
                c = self.login_states[uid].get('client')
                if c: await c.disconnect()
            except: pass
            del self.login_states[uid]

    async def _login_got_api(self, uid, text):
        parts = text.strip().split()
        if len(parts) != 2 or not parts[0].isdigit():
            send_msg(uid,
                "❌ Wrong format.\n\nSend: <code>API_ID API_HASH</code>\n"
                "Example: <code>12345678 abcdef1234567890</code>",
                kb([[{"text":"❌ Cancel","callback_data":"cancel_login"}]])); return
        self.login_states[uid].update({'api_id': int(parts[0]), 'api_hash': parts[1], 'step': 'phone'})
        send_msg(uid,
            "✅ <b>API credentials saved!</b>\n\n"
            "🔑 <b>Step 2/3: Phone Number</b>\n\n"
            "📱 Send your phone number:\n"
            "Example: <code>+917239879045</code>\n\n<i>/cancel to go back</i>",
            kb([[{"text":"❌ Cancel","callback_data":"cancel_login"}]]))

    async def _login_got_phone(self, uid, text):
        if not text.startswith('+'):
            send_msg(uid, "❌ Must include country code. Example: <code>+917239879045</code>"); return
        state = self.login_states[uid]
        send_msg(uid, "⏳ <b>Sending code…</b>")
        try:
            client = TelegramClient(StringSession(), state['api_id'], state['api_hash'])
            await client.connect()
            sent = await client.send_code_request(text.strip())
            state.update({
                'client': client, 'phone': text.strip(),
                'phone_code_hash': sent.phone_code_hash,
                'step': 'otp', 'otp_digits': ''
            })
            r = send_msg(uid,
                "📨 <b>Code sent to your Telegram!</b>\n\n"
                "🔢 <b>Step 3/3: Enter OTP</b>\n\nUse the buttons below:",
                numpad_keyboard('otp', ''))
            try: state['otp_msg_id'] = r['result']['message_id']
            except: state['otp_msg_id'] = None
        except Exception as e:
            send_msg(uid,
                f"❌ <b>Failed to send code:</b>\n<code>{e}</code>\n\n"
                "Check your API_ID / API_HASH and try again.",
                kb([[{"text":"🔑 Try Again","callback_data":"login"},
                     {"text":"🏠 Dashboard","callback_data":"dashboard"}]]))
            await self._cleanup_login(uid)

    async def _handle_numpad(self, event, uid, mid, data, prefix):
        if uid not in self.login_states:
            await event.answer(); return
        state  = self.login_states[uid]
        action = data[len(prefix)+1:]
        key    = 'otp_digits'
        if key not in state: state[key] = ''

        if   action == 'display': await event.answer(); return
        elif action == 'del':
            state[key] = state[key][:-1]; await event.answer("⌫")
        elif action == 'submit':
            await event.answer()
            if not state[key]:
                await event.answer("❌ Nothing entered!", alert=True); return
            await self._submit_otp(uid, mid, state[key]); return
        elif action.isdigit():
            if len(state[key]) < 10: state[key] += action
            await event.answer(state[key])
        else:
            await event.answer(); return

        digits = state[key]
        try:
            edit_msg(uid, mid,
                f"📨 <b>Enter OTP:</b>\n\nCode so far: <code>{digits or '—'}</code>",
                numpad_keyboard(prefix, digits))
        except: pass

    async def _submit_otp(self, uid, mid, code):
        state = self.login_states.get(uid)
        if not state: return
        try:
            await state['client'].sign_in(state['phone'], code,
                                           phone_code_hash=state['phone_code_hash'])
            await self._complete_login(uid, state, mid)
        except SessionPasswordNeededError:
            state['step'] = '2fa'
            edit_msg(uid, mid,
                "🔐 <b>2FA Enabled!</b>\n\n"
                "✍️ Type your 2FA password and send it as a message.\n"
                "<i>/cancel to go back</i>",
                kb([[{"text":"❌ Cancel Login","callback_data":"cancel_login"}]]))
        except Exception as e:
            edit_msg(uid, mid,
                f"❌ <b>Wrong code:</b> <code>{e}</code>\n\nTap Login again for a fresh code.",
                kb([[{"text":"🔑 Try Again","callback_data":"login"},
                     {"text":"🏠 Dashboard","callback_data":"dashboard"}]]))
            await self._cleanup_login(uid)

    async def _login_got_2fa(self, uid, text):
        state = self.login_states.get(uid)
        if not state: return
        try:
            await state['client'].sign_in(password=text)
            await self._complete_login(uid, state, mid=None)
        except Exception as e:
            send_msg(uid,
                f"❌ <b>Wrong 2FA password:</b> <code>{e}</code>\n\nType and send again:",
                kb([[{"text":"❌ Cancel Login","callback_data":"cancel_login"}]]))

    async def _complete_login(self, uid, state, mid):
        live_client = state['client']
        phone    = state['phone']
        api_id   = state['api_id']
        api_hash = state['api_hash']
        session  = live_client.session.save()

        self.db.save_session(uid, phone, api_id, api_hash, session)
        del self.login_states[uid]
        self.logger.log(uid, f"✅ Free login: {phone}")

        notify = (
            "✅ <b>Login Successful!</b>\n\n"
            f"📱 Account: <code>{phone}</code>\n\n"
            "🏷️ Setting branding on your account…"
        )
        if mid: edit_msg(uid, mid, notify)
        else:   send_msg(uid, notify)

        ok = await self.apply_branding_on_live_client(uid, live_client)

        try: await live_client.disconnect()
        except: pass

        # Log to user via logger bot
        user_log(uid,
            f"✅ <b>Account Added Successfully</b>\n"
            f"📱 Phone: <code>{phone}</code>\n"
            f"🏷️ Branding: {'✅ Applied' if ok else '⚠️ Failed — add manually'}\n"
            f"🕐 Time: {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}")

        if ok:
            send_msg(uid,
                "✅ <b>Account Ready!</b>\n\n"
                f"🏷️ Last name updated:\n<code>{FREE_BRANDING_LASTNAME}</code>\n\n"
                "⚠️ Do <b>NOT</b> remove it — 3 strikes = permanent ban\n"
                "💎 Upgrade to remove branding requirement!",
                kb([[{"text":"💬 Set Ad Message","callback_data":"setmessage"}],
                    [{"text":"🏠 Dashboard","callback_data":"dashboard"}]]))
        else:
            send_msg(uid,
                "✅ <b>Login Successful!</b>\n\n"
                "⚠️ Branding could not be set automatically.\n"
                f"Please add manually to your last name:\n<code>{FREE_BRANDING_LASTNAME}</code>",
                kb([[{"text":"🏠 Dashboard","callback_data":"dashboard"}]]))

    # ─── CAMPAIGN ──────────────────────────────────────────────────────────
    async def run_campaign(self, uid):
        try:
            user   = self.db.get_user(uid)
            phone  = user[1]
            client = TelegramClient(StringSession(user[4]), user[2], user[3])
            await client.connect()
            if not await client.is_user_authorized():
                send_msg(uid, "❌ Session expired. Please logout and login again.")
                user_log(uid, f"❌ Session expired for <code>{phone}</code> — please re-login.")
                self.db.set_campaign_status(uid, 0); await client.disconnect(); return

            dialogs = await client.get_dialogs()
            groups  = [d for d in dialogs if d.is_group][:FREE_MAX_GROUPS]
            if not groups:
                send_msg(uid, "❌ No groups found!")
                self.db.set_campaign_status(uid, 0); await client.disconnect(); return

            send_msg(uid, f"📊 <b>Ready!</b> Found <b>{len(groups)}</b> groups — starting…")
            round_num = 0
            campaign_start = datetime.now()

            while self.db.get_user(uid)[6]:
                runtime         = self.db.get_runtime_today(uid)
                elapsed_session = (datetime.now()-campaign_start).total_seconds()
                total_today     = runtime + elapsed_session
                if total_today >= FREE_MAX_RUNTIME:
                    self.db.set_campaign_status(uid, 0)
                    self.db.add_runtime(uid, int(elapsed_session))
                    if uid in self.campaign_start_times: del self.campaign_start_times[uid]
                    send_msg(uid, "⏰ <b>8h Daily Limit Reached!</b>\n\nResumes tomorrow.", upgrade_keyboard())
                    user_log(uid,
                        f"⏰ <b>Daily limit reached</b>\n"
                        f"📱 <code>{phone}</code> — 8h used today. Resumes tomorrow.")
                    break

                round_num += 1
                sent = failed = 0
                msg  = self.db.get_user(uid)[5]

                for group in groups:
                    if not self.db.get_user(uid)[6]: break
                    elapsed = (datetime.now()-campaign_start).total_seconds()
                    if runtime + elapsed >= FREE_MAX_RUNTIME: break
                    try:
                        await client.send_message(group.entity, msg)
                        sent += 1
                        # ── Per-message log to user ──
                        user_log(uid,
                            f"[<code>{phone}</code>] "
                            f"[✓] Sent to <b>{group.name}</b> ({group.entity.id})")
                        await asyncio.sleep(FREE_MSG_DELAY)
                    except FloodWaitError as e:
                        send_msg(uid, f"⚠️ FloodWait {e.seconds}s — pausing…")
                        user_log(uid, f"[<code>{phone}</code>] ⚠️ FloodWait {e.seconds}s")
                        await asyncio.sleep(e.seconds)
                    except Exception as ex:
                        failed += 1
                        # ── Per-message fail log to user ──
                        user_log(uid,
                            f"[<code>{phone}</code>] "
                            f"[✗] Failed to <b>{group.name}</b> ({group.entity.id}): {ex}")
                        await asyncio.sleep(10)

                hl = max(0, 8-(runtime+elapsed_session)/3600)
                now_str = datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')
                send_msg(uid,
                    f"📊 <b>Round {round_num}</b> — ✅ {sent}  ❌ {failed}\n"
                    f"⏳ {hl:.1f}h left  |  Next in {FREE_CYCLE_DELAY//60}m",
                    kb([[{"text":"🛑 Stop","callback_data":"stopcampaign"},
                         {"text":"💎 Upgrade","callback_data":"upgrade"}]]))
                user_log(uid,
                    f"📊 <b>Round {round_num} complete</b>\n"
                    f"📱 <code>{phone}</code>\n"
                    f"✅ Sent: {sent}  ❌ Failed: {failed}\n"
                    f"⏳ {hl:.1f}h left today\n"
                    f"🕐 {now_str}")
                await asyncio.sleep(FREE_CYCLE_DELAY)

            await client.disconnect()

        except asyncio.CancelledError:
            if uid in self.campaign_start_times:
                elapsed = (datetime.now()-self.campaign_start_times[uid]).total_seconds()
                self.db.add_runtime(uid, int(elapsed)); del self.campaign_start_times[uid]
            user_log(uid,
                f"🛑 <b>Campaign stopped</b>\n"
                f"📱 <code>{self.db.get_user(uid)[1] if self.db.get_user(uid) else 'N/A'}</code>\n"
                f"🕐 {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}")
        except Exception as e:
            self.db.set_campaign_status(uid, 0)
            if uid in self.tasks: del self.tasks[uid]
            send_msg(uid, f"❌ Campaign error: <code>{e}</code>")
            user_log(uid, f"❌ <b>Campaign error</b>\n<code>{e}</code>")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
async def main():
    print("="*50+"\n  🆓 UZERON ADSBOT — Free Tier\n"+"="*50)
    missing = [v for v in ['API_ID','API_HASH','FREE_BOT_TOKEN','LOGGER_BOT_TOKEN',
                            'ADMIN_IDS','DATABASE_URL']
               if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}"); sys.exit(1)
    await UzeronFreeBot().start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🆓 Stopped")
    except Exception as e:
        print(f"Fatal: {e}"); sys.exit(1)
