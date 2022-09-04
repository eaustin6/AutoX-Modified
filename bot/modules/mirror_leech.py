from base64 import b64encode
from re import match as re_match, split as re_split
from os import path as ospath
from time import sleep, time
from threading import Thread
from telegram.ext import CommandHandler, MessageHandler, Filters
from requests import get as rget
from bot import dispatcher, DOWNLOAD_DIR, LOGGER
from bot.helper.ext_utils.bot_utils import is_url, is_magnet, is_mega_link, is_gdrive_link, get_content_type
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.aria2_download import add_aria2c_download
from bot.helper.mirror_utils.download_utils.gd_downloader import add_gd_download
from bot.helper.mirror_utils.download_utils.qbit_downloader import QbDownloader
from bot.helper.mirror_utils.download_utils.mega_downloader import add_mega_download
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage
from .listener import MirrorLeechListener


def _mirror_leech(bot, message, isZip=False, extract=False, isQbit=False, isLeech=False):
    message = message.message if message.message is not None else message.channel_post
    from_user = message.from_user if message.sender_chat is None else message.sender_chat
    chat_id = message.chat.id
    mesg = f"/jv {message.text}".split('\n') if message.text else "".split('\n')
    message_args = mesg[0].split(maxsplit=1)
    name_args = mesg[0].split('|', maxsplit=1)
    index = 1
    ratio = None
    seed_time = None
    select = False
    seed = False
    multi = 0

    if len(message_args) > 1:
        args = mesg[0].split(maxsplit=3)
        for x in args:
            x = x.strip()
            if x == 's':
               select = True
               index += 1
            elif x == 'd':
                seed = True
                index += 1
            elif x.startswith('d:'):
                seed = True
                index += 1
                dargs = x.split(':')
                ratio = dargs[1] if dargs[1] else None
                if len(dargs) == 3:
                    seed_time = dargs[2] if dargs[2] else None
            elif x.isdigit():
                multi = int(x)
                mi = index
        if multi == 0:
            message_args = mesg[0].split(maxsplit=index)
            if len(message_args) > index:
                link = message_args[index].strip()
                if link.startswith(("|", "pswd:")):
                    link = ''
            else:
                link = ''
        else:
            link = ''
    else:
        link = ''

    if len(name_args) > 1:
        name = name_args[1]
        name = name.split(' pswd:')[0]
        name = name.strip()
    else:
        name = ''

    link = re_split(r"pswd:|\|", link)[0]
    link = link.strip()

    pswd_arg = mesg[0].split(' pswd: ')
    if len(pswd_arg) > 1:
        pswd = pswd_arg[1]
    else:
        pswd = None

    if from_user.username:
        tag = f"@{from_user.username}"
    else:
        tag = (
        f'<a href="tg://user?id={from_user.id}">{from_user.first_name}</a>' if
        message.chat.type !="channel" else 
        f'<a href="https://t.me/c/{str(from_user.id)[4:]}">{from_user.title}</a>'
    )
    file = None
    if message.document is not None:
        file = message.document
    if is_magnet(link) or file is not None:
        isQbit = True
    if (
        not is_url(link)
        and not is_magnet(link)
        and file is not None
    ):

        if isQbit:
            file_name = str(time()).replace(".", "") + ".torrent"
            link = file.get_file().download(custom_path=file_name)
        elif file.mime_type != "application/x-bittorrent":
            listener = MirrorListener(bot, message, isZip, extract, isQbit, isLeech, pswd, tag)
            tg_downloader = TelegramDownloadHelper(listener)
            ms = msg
            tg_downloader.add_download(ms, f'{DOWNLOAD_DIR}{listener.uid}/', name)
            return
        else:
            link = file.get_file().file_path

    if not is_mega_link(link) and not isQbit and not is_magnet(link) \
        and not is_gdrive_link(link) and not link.endswith('.torrent'):
        content_type = get_content_type(link)
        if content_type is None or re_match(r'text/html|text/plain', content_type):
            try:
                link = direct_link_generator(link)
                LOGGER.info(f"Generated link: {link}")
            except DirectDownloadLinkException as e:
                LOGGER.info(str(e))
                if str(e).startswith('ERROR:'):
                    return sendMessage(str(e), bot, message)
    elif isQbit and not is_magnet(link) and not ospath.exists(link):
        if link.endswith('.torrent') or "https://api.telegram.org/file/" in link:
            content_type = None
        else:
            content_type = get_content_type(link)
        if content_type is None or re_match(r'application/x-bittorrent|application/octet-stream', content_type):
            try:
                resp = rget(link, timeout=10, headers = {'user-agent': 'Wget/1.12'})
                if resp.status_code == 200:
                    file_name = str(time()).replace(".", "") + ".torrent"
                    with open(file_name, "wb") as t:
                        t.write(resp.content)
                    link = str(file_name)
                else:
                    return sendMessage(f"{tag} ERROR: link got HTTP response: {resp.status_code}", bot, message)
            except Exception as e:
                error = str(e).replace('<', ' ').replace('>', ' ')
                if error.startswith('No connection adapters were found for'):
                    link = error.split("'")[1]
                else:
                    LOGGER.error(str(e))
                    return sendMessage(tag + " " + error, bot, message)
        else:
            msg = "Qb commands for torrents only. if you are trying to dowload torrent then report."
            return sendMessage(msg, bot, message)

    listener = MirrorLeechListener(bot, message, isZip, extract, isQbit, isLeech, pswd, tag, select, seed)

    if is_gdrive_link(link):
        if not isZip and not extract and not isLeech:
            gmsg = f"Use /{BotCommands.CloneCommand} to clone Google Drive file/folder\n\n"
            gmsg += f"Use /{BotCommands.ZipMirrorCommand[0]} to make zip of Google Drive folder\n\n"
            gmsg += f"Use /{BotCommands.UnzipMirrorCommand[0]} to extracts Google Drive archive folder/file"
            sendMessage(gmsg, bot, message)
        else:
            Thread(target=add_gd_download, args=(link, f'{DOWNLOAD_DIR}{listener.uid}', listener, name)).start()
    elif is_mega_link(link):
        Thread(target=add_mega_download, args=(link, f'{DOWNLOAD_DIR}{listener.uid}/', listener, name)).start()
    elif isQbit and (is_magnet(link) or ospath.exists(link)):
        Thread(target=QbDownloader(listener).add_qb_torrent, args=(link, f'{DOWNLOAD_DIR}{listener.uid}',
                                                                   select, ratio, seed_time)).start()
    else:
        if len(mesg) > 1:
            ussr = mesg[1]
            if len(mesg) > 2:
                pssw = mesg[2]
            else:
                pssw = ''
            auth = f"{ussr}:{pssw}"
            auth = "Basic " + b64encode(auth.encode()).decode('ascii')
        else:
            auth = ''
        Thread(target=add_aria2c_download, args=(link, f'{DOWNLOAD_DIR}{listener.uid}', listener, name,
                                                 auth, select, ratio, seed_time)).start()

    if multi > 1:
        sleep(4)
        nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
        msg = message.text.split(maxsplit=mi+1)
        msg[mi] = f"{multi - 1}"
        nextmsg = sendMessage(" ".join(msg), bot, nextmsg)
        nextmsg.from_user.id = from_user.id
        sleep(4)
        Thread(target=_mirror_leech, args=(bot, nextmsg, isZip, extract, isQbit, isLeech)).start()


def leech(update, context):
    _mirror_leech(context.bot, update, isLeech=True)

def qb_leech(update, context):
    _mirror_leech(context.bot, update, isQbit=True, isLeech=True)


leech_handler = MessageHandler(CustomFilters.mirror_uris & Filters.chat_type, leech, run_async=True)
qb_leech_handler = MessageHandler(CustomFilters.mirror_torrent_and_magnets & Filters.chat_type, qb_leech, run_async=True)


dispatcher.add_handler(leech_handler)
dispatcher.add_handler(qb_leech_handler)
