import os
import re
import time
import threading
import telebot
from telebot import types
import yt_dlp

# --- CONFIGURATION (INTEGRATED) ---
BOT_TOKEN = "8897254785:AAFNq-FOs-2IC5jF6erDjwHTPRpzOqeXVrU"
CHANNEL_INVITE_LINK = "https://t.me/+cNnl3zkRZjc3NjI1"

bot = telebot.TeleBot(BOT_TOKEN)

# Dynamic Channel Cache to avoid hardcoding the negative ID
CACHED_CHANNEL_ID = None

# Global dictionary to track user steps and messages to delete
USER_DATA = {}

# --- CONSTANTS & REGEX ---
CREDIT = "\n\nPowered By @TheAsik067"

PLATFORMS = {
    "instagram": {"name": "Instagram", "regex": r"(https?://)?(www\.)?(instagram\.com)/.+", "icon": "📸"},
    "youtube": {"name": "YouTube", "regex": r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", "icon": "🎥"},
    "tiktok": {"name": "TikTok", "regex": r"(https?://)?(www\.)?(tiktok\.com)/.+", "icon": "🎵"},
    "facebook": {"name": "Facebook", "regex": r"(https?://)?(www\.)?(facebook\.com|fb\.watch)/.+", "icon": "📘"}
}

# --- HELPER FUNCTIONS ---

def get_channel_id():
    """Dynamically resolves the numeric Channel ID using the invite link to prevent setup errors."""
    global CACHED_CHANNEL_ID
    if CACHED_CHANNEL_ID:
        return CACHED_CHANNEL_ID
    try:
        chat = bot.get_chat(CHANNEL_INVITE_LINK)
        CACHED_CHANNEL_ID = chat.id
        return CACHED_CHANNEL_ID
    except Exception:
        # Fallback to general manual verification lookup if direct invite parsing fails
        return None

def init_user(user_id):
    if user_id not in USER_DATA:
        USER_DATA[user_id] = {"platform": None, "link": None, "msgs_to_delete": []}

def track_msg(user_id, message_id):
    init_user(user_id)
    USER_DATA[user_id]["msgs_to_delete"].append(message_id)

def cleanup_messages(user_id):
    if user_id in USER_DATA:
        for msg_id in USER_DATA[user_id]["msgs_to_delete"]:
            try:
                bot.delete_message(user_id, msg_id)
            except Exception:
                pass
        USER_DATA[user_id]["msgs_to_delete"] = []

def delayed_delete(chat_id, message_id, delay=1200):
    def target():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
    threading.Thread(target=target, daemon=True).start()

def check_subscription(user_id):
    target_channel = get_channel_id()
    if not target_channel:
        # If bot cannot fetch channel directly, bypass to prevent crashing the whole bot
        return True
    try:
        member = bot.get_chat_member(target_channel, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception:
        pass
    return False

# --- FORCE SUBSCRIBE SYSTEM ---

def send_force_sub_msg(chat_id, user_first_name):
    text = f"👋 Welcome {user_first_name}\n\n📢 Join Channel ✅\nThen click Verify to Unlock the Downloader Bot.{CREDIT}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 JOIN PRIVATE CHANNEL", url=CHANNEL_INVITE_LINK))
    markup.add(types.InlineKeyboardButton("🔄 Verify / Check Again", callback_data="verify_sub"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    init_user(user_id)
    cleanup_messages(user_id)
    
    if not check_subscription(user_id):
        send_force_sub_msg(message.chat.id, message.from_user.first_name)
    else:
        send_platform_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "verify_sub")
def verify_callback(call):
    user_id = call.from_user.id
    if check_subscription(user_id):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_platform_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ You have not joined yet! Please join and try again.", show_alert=True)

# --- PLATFORM SELECTION ---

def send_platform_menu(chat_id):
    cleanup_messages(chat_id)
    text = f"✨ Select Your Social Media Platform{CREDIT}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(f"{info['icon']} {info['name']}", callback_data=f"plat_{k}") for k, info in PLATFORMS.items()]
    markup.add(*buttons)
    msg = bot.send_message(chat_id, text, reply_markup=markup)
    track_msg(chat_id, msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("plat_"))
def platform_callback(call):
    user_id = call.from_user.id
    if not check_subscription(user_id):
        send_force_sub_msg(call.message.chat.id, call.from_user.first_name)
        return
        
    platform_key = call.data.replace("plat_", "")
    if platform_key in PLATFORMS:
        init_user(user_id)
        USER_DATA[user_id]["platform"] = platform_key
        
        text = f"📥 You selected {PLATFORMS[platform_key]['name']}\n\n🔗 Please send your link.{CREDIT}"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
        except Exception:
            msg = bot.send_message(call.message.chat.id, text)
            track_msg(user_id, msg.message_id)

# --- LINK VALIDATION & QUALITY ---

@bot.message_handler(func=lambda message: True)
def handle_links(message):
    user_id = message.from_user.id
    init_user(user_id)
    track_msg(user_id, message.message_id)
    
    if not check_subscription(user_id):
        send_force_sub_msg(message.chat.id, message.from_user.first_name)
        return

    platform_key = USER_DATA[user_id].get("platform")
    if not platform_key:
        send_platform_menu(message.chat.id)
        return

    url = message.text.strip()
    regex = PLATFORMS[platform_key]["regex"]
    
    if not re.match(regex, url, re.IGNORECASE):
        err_msg = bot.send_message(message.chat.id, f"❌ Invalid Link!\n\nPlease send a valid {PLATFORMS[platform_key]['name']} link.{CREDIT}")
        time.sleep(3)
        try: bot.delete_message(message.chat.id, err_msg.message_id) except Exception: pass
        return

    USER_DATA[user_id]["link"] = url
    
    text = f"📥 Link Received!\n\nSelect Video Quality{CREDIT}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 1080p", callback_data="q_1080"),
        types.InlineKeyboardButton("🎬 720p", callback_data="q_720"),
        types.InlineKeyboardButton("⚡ 480p", callback_data="q_480"),
        types.InlineKeyboardButton("⚡ 360p", callback_data="q_360")
    )
    msg = bot.send_message(message.chat.id, text, reply_markup=markup)
    track_msg(user_id, msg.message_id)

# --- DOWNLOAD & PROCESSING ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("q_"))
def quality_callback(call):
    user_id = call.from_user.id
    if not check_subscription(user_id):
        send_force_sub_msg(call.message.chat.id, call.from_user.first_name)
        return

    height = call.data.replace("q_", "")
    url = USER_DATA[user_id].get("link")
    
    if not url:
        bot.answer_callback_query(call.id, "Error: Link missed. Please try again.")
        send_platform_menu(call.message.chat.id)
        return

    proc_msg = bot.send_message(call.message.chat.id, f"⚡ Processing Your Download Request...\n\nPlease wait.{CREDIT}")
    cleanup_messages(user_id)
    
    threading.Thread(target=download_and_send_worker, args=(call.message.chat.id, user_id, url, height, proc_msg.message_id), daemon=True).start()

def download_and_send_worker(chat_id, user_id, url, height, proc_msg_id):
    out_template = f"downloads/{user_id}_{int(time.time())}.%(ext)s"
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True
    }

    filepath = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if not os.path.exists(filepath):
                base, _ = os.path.splitext(filepath)
                filepath = base + ".mp4"

        if os.path.exists(filepath):
            with open(filepath, 'rb') as video_file:
                sent_msg = bot.send_video(
                    chat_id, 
                    video_file, 
                    caption=f"🎉 Video Downloaded Successfully!{CREDIT}"
                )
            try: bot.delete_message(chat_id, proc_msg_id) except Exception: pass
            delayed_delete(chat_id, sent_msg.message_id, 1200)
        else:
            raise FileNotFoundError

    except Exception:
        try: bot.delete_message(chat_id, proc_msg_id) except Exception: pass
        err_msg = bot.send_message(chat_id, f"❌ Download Failed!\nPlease try again later.{CREDIT}")
        time.sleep(4)
        try: bot.delete_message(chat_id, err_msg.message_id) except Exception: pass
        
    finally:
        if filepath and os.path.exists(filepath):
            try: os.remove(filepath) except Exception: pass
        USER_DATA[user_id] = {"platform": None, "link": None, "msgs_to_delete": []}
        send_platform_menu(chat_id)

# --- STARTUP ---
if __name__ == "__main__":
    print("Ashik Downloader Bot is running...")
    bot.infinity_polling()
              
