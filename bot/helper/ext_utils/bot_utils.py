from re import findall as re_findall, match as re_match
from threading import Thread, Event
from time import time, sleep
from math import ceil
from html import escape
from psutil import virtual_memory, cpu_percent, disk_usage, net_io_counters
from requests import head as rhead
from urllib.request import urlopen
from telegram import InlineKeyboardMarkup
from telegram.message import Message
from telegram.ext import CallbackQueryHandler

from bot import download_dict, download_dict_lock, STATUS_LIMIT, botStartTime, DOWNLOAD_DIR, WEB_PINCODE, BASE_URL, status_reply_dict, status_reply_dict_lock, dispatcher, bot, OWNER_ID, Interval
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

COUNT = 0
PAGE_NO = 1


class MirrorStatus:
    STATUS_UPLOADING = "Upload📤"
    STATUS_DOWNLOADING = "Download📤"
    STATUS_CLONING = "Clone♻️"
    STATUS_WAITING = "Queue💤"
    STATUS_PAUSED = "Pause⛔️"
    STATUS_ARCHIVING = "Archive🔐"
    STATUS_EXTRACTING = "Extract📂"
    STATUS_SPLITTING = "Split✂️"
    STATUS_CHECKING = "CheckUp📝"
    STATUS_SEEDING = "Seed🌧"
  
class EngineStatus:
    STATUS_ARIA = "Aria2c📶"
    STATUS_GDRIVE = "Google API♻️"
    STATUS_MEGA = "Mega API⭕️"
    STATUS_QB = "qBittorrent🦠"
    STATUS_TG = "Pyrogram💥"
    STATUS_YT = "Yt-dlp🌟"
    STATUS_EXT = "extract | pextract⚔️"
    STATUS_SPLIT = "FFmpeg✂️"
    STATUS_ZIP = "7z🛠"

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

PROGRESS_MAX_SIZE = 100 // 10 
PROGRESS_INCOMPLETE = ['◔', '◔', '◑', '◑', '◑', '◕', '◕']

class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = Event()
        thread = Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time() + self.interval
        while not self.stopEvent.wait(nextTime - time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'

def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in list(download_dict.values()):
            if dl.gid() == gid:
                return dl
    return None

def getAllDownload(req_status: str):
    with download_dict_lock:
        for dl in list(download_dict.values()):
            status = dl.status()
            if req_status in ['all', status]:
                return dl
    return None

def bt_selection_buttons(id_: str):
    if len(id_) > 20:
        gid = id_[:12]
    else:
        gid = id_

    pincode = ""
    for n in id_:
        if n.isdigit():
            pincode += str(n)
        if len(pincode) == 4:
            break

    buttons = ButtonMaker()
    if WEB_PINCODE:
        buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{id_}")
        buttons.sbutton("Pincode", f"btsel pin {gid} {pincode}")
    else:
        buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{id_}?pin_code={pincode}")
    buttons.sbutton("Done Selecting", f"btsel done {gid} {id_}")
    return buttons.build_menu(2)

def get_progress_bar_string(status):
    completed = status.processed_bytes() / 8
    total = status.size_raw() / 8
    p = 0 if total == 0 else round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 8
    cPart = p % 8 - 1
    p_str = '●' * cFull
    if cPart >= 0:
        p_str += PROGRESS_INCOMPLETE[cPart]
    p_str += '○' * (PROGRESS_MAX_SIZE - cFull)
    p_str = f"「{p_str}」"
    return p_str

def progress_bar(percentage):
    comp = '▓'
    ncomp = '░'
    pr = ""

    if isinstance(percentage, str):
        return "NaN"

    try:
        percentage=int(percentage)
    except:
        percentage = 0

    for i in range(1,11):
        if i <= int(percentage/10):
            pr += comp
        else:
            pr += ncomp
    return pr

def get_readable_message():
    with download_dict_lock:
        dlspeed_bytes = 0
        uldl_bytes = 0
        START = 0
        num_active = 0
        num_seeding = 0
        num_upload = 0
        for stats in list(download_dict.values()):
            if stats.status() == MirrorStatus.STATUS_DOWNLOADING:
               num_active += 1
            if stats.status() == MirrorStatus.STATUS_UPLOADING:
               num_upload += 1
            if stats.status() == MirrorStatus.STATUS_SEEDING:
               num_seeding += 1
        msg = ""
        if STATUS_LIMIT is not None:
            tasks = len(download_dict)
            global pages
            pages = ceil(tasks/STATUS_LIMIT)
            if PAGE_NO > pages and pages != 0:
                globals()['COUNT'] -= STATUS_LIMIT
                globals()['PAGE_NO'] -= 1
        msg += f"<b> DL's: {num_active} || UL's: {num_upload} || Seed's: {num_seeding} </b>\n\n<b>Active : {tasks}</b>\n\n"
        for index, download in enumerate(list(download_dict.values())[COUNT:], start=1):
            msg += f"<b><a href='{download.message.link}'>{download.status()}</a>: </b><code>{escape(str(download.name()))}</code>"
            if download.status() not in [MirrorStatus.STATUS_SPLITTING, MirrorStatus.STATUS_SEEDING]:
                msg += f"\n{get_progress_bar_string(download)} {download.progress()}"
                msg += f"\n<b>Processed:</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                msg += f"\n<b>Speed:</b> {download.speed()} | <b>ETA:</b> {download.eta()}"
                msg += f"\n<b>Elapsed: </b>{get_readable_time(time() - download.message.date.timestamp())}"
                if hasattr(download, 'seeders_num'):
                    try:
                        msg += f"\n<b>Seeders:</b> {download.seeders_num()} | <b>Leechers:</b> {download.leechers_num()}"
                        msg += f"\n<b>To Select:</b> <code>/{BotCommands.BtSelectCommand} {download.gid()}</code>"
                    except: 
                        pass
            elif download.status() == MirrorStatus.STATUS_SEEDING:
                msg += f"\n<b>Size: </b>{download.size()}"
                msg += f"\n<b>Speed: </b>{download.upload_speed()}"
                msg += f" | <b>Uploaded: </b>{download.uploaded_bytes()}"
                msg += f"\n<b>Ratio: </b>{download.ratio()}"
                msg += f" | <b>Time: </b>{download.seeding_time()}"
            else:
                msg += f"\n<b>Size: </b>{download.size()}"
            msg += f"\n<b>Engine: </b>{download.engine}"
            if download.message.chat.type != 'private':
                uname = download.from_user.first_name
                msg += f"\n<b><a href='{download.message.link}'>Source</a>:</b> {uname} | <b>Id :</b> <code>{download.from_user.id}</code>"
            else:
                msg += ''
            msg += f"\n<b>Cancel:</b> <code>/{BotCommands.CancelMirror} {download.gid()}</code>"
            msg += f"\n<b>________________________________</b>"
            msg += "\n\n"
            if STATUS_LIMIT is not None and index == STATUS_LIMIT:
                break
        if len(msg) == 0:
            return None, None
        dl_speed = 0
        up_speed = 0
        for download in list(download_dict.values()):
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                spd = download.speed()
                if 'K' in spd:
                    dl_speed += float(spd.split('K')[0]) * 1024
                elif 'M' in spd:
                    dl_speed += float(spd.split('M')[0]) * 1048576
            elif download.status() == MirrorStatus.STATUS_UPLOADING:
                spd = download.speed()
                if 'KB/s' in spd:
                    up_speed += float(spd.split('K')[0]) * 1024
                elif 'MB/s' in spd:
                    up_speed += float(spd.split('M')[0]) * 1048576
            elif download.status() == MirrorStatus.STATUS_SEEDING:
                spd = download.upload_speed()
                if 'K' in spd:
                    up_speed += float(spd.split('K')[0]) * 1024
                elif 'M' in spd:
                    up_speed += float(spd.split('M')[0]) * 1048576
        bmsg = f"<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)}"
        bmsg += f"\n<b>RAM:</b> {virtual_memory().percent}% | <b>UPTIME:</b> {get_readable_time(time() - botStartTime)}"
        bmsg += f"\n<b>DL:</b> {get_readable_file_size(dl_speed)}/s | <b>UL:</b> {get_readable_file_size(up_speed)}/s"
        buttons = ButtonMaker()
        buttons.sbutton("Refresh", str(FOUR))
        buttons.sbutton("Close", str(TWO))
        buttons.sbutton("Stats", str(THREE))
        sbutton = buttons.build_menu(3)
        if STATUS_LIMIT is not None and tasks > STATUS_LIMIT:
            msg += f"<b>Page:</b> {PAGE_NO}/{pages} | <b>Tasks:</b> {tasks}\n"
            buttons = ButtonMaker()
            buttons.sbutton("⬅️", "status pre")
            buttons.sbutton("Close", str(TWO))
            buttons.sbutton("➡️", "status nex")
            buttons.sbutton("Refresh", str(FOUR))
            buttons.sbutton("Stats", str(THREE))
            button = buttons.build_menu(3)
            return msg + bmsg, button
        return msg + bmsg, sbutton
    
def turn(data):
    try:
        with download_dict_lock:
            global COUNT, PAGE_NO
            if data[1] == "nex":
                if PAGE_NO == pages:
                    COUNT = 0
                    PAGE_NO = 1
                else:
                    COUNT += STATUS_LIMIT
                    PAGE_NO += 1
            elif data[1] == "pre":
                if PAGE_NO == 1:
                    COUNT = STATUS_LIMIT * (pages - 1)
                    PAGE_NO = pages
                else:
                    COUNT -= STATUS_LIMIT
                    PAGE_NO -= 1
        return True
    except:
        return False
    
def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result

def is_url(url: str):
    url = re_findall(URL_REGEX, url)
    return bool(url)

def is_gdrive_link(url: str):
    return "drive.google.com" in url

def is_mega_link(url: str):
    return "mega.nz" in url or "mega.co.nz" in url

def get_mega_link_type(url: str):
    if "folder" in url:
        return "folder"
    elif "file" in url:
        return "file"
    elif "/#F!" in url:
        return "folder"
    return "file"

def is_magnet(url: str):
    magnet = re_findall(MAGNET_REGEX, url)
    return bool(magnet)

def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper

def get_content_type(link: str) -> str:
    try:
        res = rhead(link, allow_redirects=True, timeout=5, headers = {'user-agent': 'Wget/1.12'})
        content_type = res.headers.get('content-type')
    except:
        try:
            res = urlopen(link, timeout=5)
            info = res.info()
            content_type = info.get_content_type()
        except:
            content_type = None
    return content_type

ONE, TWO, THREE, FOUR = range(4)

def close(update, context):  
    chat_id  = update.effective_chat.id
    user_id = update.callback_query.from_user.id
    bot = context.bot
    query = update.callback_query
    admins = bot.get_chat_member(chat_id, user_id).status in ['creator', 'administrator'] or user_id in [OWNER_ID] 
    if admins: 
        query.answer()  
        query.message.delete() 
    else:  
        query.answer(text="Nice Try, Get Lost🥱.\n\nOnly Admins can use this.", show_alert=True)
        
def stats(update, context):
    query = update.callback_query
    stats = bot_sys_stats()
    query.answer(text=stats, show_alert=True)

def bot_sys_stats():
    currentTime = get_readable_time(time() - botStartTime)
    cpu = cpu_percent(interval=0.5)
    memory = virtual_memory()
    mem = memory.percent
    total, used, free, disk= disk_usage('/')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    recv = get_readable_file_size(net_io_counters().bytes_recv)
    sent = get_readable_file_size(net_io_counters().bytes_sent)
    stats = f"""
BOT UPTIME⏰: {currentTime}

CPU: {progress_bar(cpu)} {cpu}%
RAM: {progress_bar(mem)} {mem}%
DISK: {progress_bar(disk)} {disk}%

TOTAL: {total}

USED: {used} || FREE: {free}
SENT: {sent} || RECV: {recv}

#KaipullaX
"""
    return stats

def editMessage(text: str, message: Message, reply_markup=None):
    try:
        bot.editMessageText(text=text, message_id=message.message_id,
                              chat_id=message.chat.id,reply_markup=reply_markup,
                              parse_mode='HTML', disable_web_page_preview=True)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return editMessage(text, message, reply_markup)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)
    
def update_all_messages(force=False):
    with status_reply_dict_lock:
        if not force and (not status_reply_dict or not Interval or time() - list(status_reply_dict.values())[0][1] < 3):
            return
        for chat_id in status_reply_dict:
            status_reply_dict[chat_id][1] = time()

    msg, buttons = get_readable_message()
    if msg is None:
        return
    with status_reply_dict_lock:
        for chat_id in status_reply_dict:
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id][0].text:
                if buttons == "":
                    rmsg = editMessage(msg, status_reply_dict[chat_id][0])
                else:
                    rmsg = editMessage(msg, status_reply_dict[chat_id][0], buttons)
                if rmsg == "Message to edit not found":
                    del status_reply_dict[chat_id]
                    return
                status_reply_dict[chat_id][0].text = msg
                status_reply_dict[chat_id][1] = time()
def refresh(update, context):
    chat_id  = update.effective_chat.id
    query = update.callback_query
    user_id = update.callback_query.from_user.id
    first = update.callback_query.from_user.first_name
    query.edit_message_text(text=f"{first} Refreshing...👻")
    sleep(2)
    update_all_messages()
    query.answer(text="Refreshed", show_alert=False)
    
dispatcher.add_handler(CallbackQueryHandler(close, pattern='^' + str(TWO) + '$'))
dispatcher.add_handler(CallbackQueryHandler(stats, pattern='^' + str(THREE) + '$'))
dispatcher.add_handler(CallbackQueryHandler(refresh, pattern='^' + str(FOUR) + '$'))
