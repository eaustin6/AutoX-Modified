from logging import getLogger, ERROR
from os import remove as osremove, walk, path as ospath, rename as osrename
from time import time, sleep
from pyrogram.errors import FloodWait, RPCError
import requests
from PIL import Image
from threading import RLock

from bot import AS_DOCUMENT, AS_DOC_USERS, AS_MEDIA_USERS, CUSTOM_FILENAME, EXTENSION_FILTER, DUMP_CHAT, app
from bot.helper.ext_utils.fs_utils import take_ss, get_media_info, get_media_streams, clean_unwanted
from bot.helper.ext_utils.bot_utils import get_readable_file_size

LOGGER = getLogger(__name__)
getLogger("pyrogram").setLevel(ERROR)

IMAGE_SUFFIXES = ("JPG", "JPX", "PNG", "CR2", "TIF", "BMP", "JXR", "PSD", "ICO", "HEIC", "JPEG")

def DownLoadFile(url):
    file_name = str(time()) + ".jpg"
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=128):
            fd.write(chunk)
    return file_name

class TgUploader:

    def __init__(self, name=None, path=None, size=0, listener=None):
        self.name = name
        self.uploaded_bytes = 0
        self._last_uploaded = 0
        self.__listener = listener
        self.__path = path
        self.__start_time = time()
        self.__total_files = 0
        self.__is_cancelled = False
        self.__as_doc = AS_DOCUMENT
        self.__thumb = f"Thumbnails/{listener.from_user.id}.jpg"
        self.__msgs_dict = {}
        self.__corrupted = 0
        self.__resource_lock = RLock()
        self.__is_corrupted = False
        self.__size = size
        self.__msg_to_reply()
        self.__user_settings()

    def upload(self, o_files):
        for dirpath, subdir, files in sorted(walk(self.__path)):
            for file_ in sorted(files):
                if file_ in o_files:
                    continue
                if not file_.lower().endswith(tuple(EXTENSION_FILTER)):
                    up_path = ospath.join(dirpath, file_)
                    self.__total_files += 1
                    try:
                        if ospath.getsize(up_path) == 0:
                            LOGGER.error(f"{up_path} size is zero, telegram don't upload zero size files")
                            self.__corrupted += 1
                            continue
                    except Exception as e:
                        if self.__is_cancelled:
                            return
                        else:
                            LOGGER.error(e)
                            continue
                    self.__upload_file(up_path, file_, dirpath)
                    if self.__is_cancelled:
                        return
                    #if (not self.__listener.isPrivate or DUMP_CHAT is not None) and not self.__is_corrupted:
                    #    self.__msgs_dict[self.__sent_msg.link] = file_
                    self._last_uploaded = 0
                    sleep(1)
        if self.__listener.seed and not self.__listener.newDir:
            clean_unwanted(self.__path)
        if self.__total_files <= self.__corrupted:
            return self.__listener.onUploadError('Files Corrupted. Check logs')
        LOGGER.info(f"Leech Completed: {self.name}")
        size = get_readable_file_size(self.__size)
        self.__listener.onUploadComplete(None, size, self.__msgs_dict, self.__total_files, self.__corrupted, self.name)

    def __upload_file(self, up_path, file_, dirpath):
        if file_.startswith('www'):  
            file_ = ' '.join(file_.split()[1:])
            id = Id = self.__listener.from_user.id
            if -1001658368532 == id:
               file_ = '@KaipullaX1 -' + file_.strip('-').strip('_')
               thumb_url = "https://telegra.ph/file/49a0ace8ed3ffbb37d5a8.jpg"
               self.__thumb = DownLoadFile(thumb_url)
            elif 2113726835 == id:
               file_ = '@KaipullaX1 -' + file_.strip('-').strip('_')
            else:
               file_ = '' + file_.strip('-').strip('_')
            new_path = ospath.join(dirpath, file_)
            osrename(up_path, new_path)
            up_path = new_path
        cap_mono = f"<b>{file_.rsplit('.', 1)[0]}</b>"
        notMedia = False
        thumb = self.__thumb
        self.__is_corrupted = False
        try:
            is_video, is_audio = get_media_streams(up_path)
            if not self.__as_doc:
                if is_video:
                    duration = get_media_info(up_path)[0]
                    if thumb is None:
                        thumb = take_ss(up_path, duration)
                        if self.__is_cancelled:
                            if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                                osremove(thumb)
                            return
                    if thumb is not None:
                        with Image.open(thumb) as img:
                            width, height = img.size
                    else:
                        width = 480
                        height = 320
                    if not file_.upper().endswith(("MKV", "MP4")):
                        file_ = f"{ospath.splitext(file_)[0]}.mp4"
                        new_path = ospath.join(dirpath, file_)
                        osrename(up_path, new_path)
                        up_path = new_path
                    self.__sent_msg = self.__sent_msg.reply_video(video=up_path,
                                                                  quote=True,
                                                                  caption=cap_mono,
                                                                  duration=duration,
                                                                  width=width,
                                                                  height=height,
                                                                  thumb=thumb,
                                                                  supports_streaming=True,
                                                                  disable_notification=True,
                                                                  progress=self.__upload_progress)
                elif is_audio:
                    duration , artist, title = get_media_info(up_path)
                    self.__sent_msg = self.__sent_msg.reply_audio(audio=up_path,
                                                                  quote=True,
                                                                  caption=cap_mono,
                                                                  duration=duration,
                                                                  performer=artist,
                                                                  title=title,
                                                                  thumb=thumb,
                                                                  disable_notification=True,
                                                                  progress=self.__upload_progress)
                elif file_.upper().endswith(IMAGE_SUFFIXES):
                    self.__sent_msg = self.__sent_msg.reply_photo(photo=up_path,
                                                                  quote=True,
                                                                  caption=cap_mono,
                                                                  disable_notification=True,
                                                                  progress=self.__upload_progress)
                else:
                    notMedia = True
            if self.__as_doc or notMedia:
                if is_video and thumb is None:
                    thumb = take_ss(up_path, None)
                    if self.__is_cancelled:
                        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                            osremove(thumb)
                        return
                self.__sent_msg = self.__sent_msg.reply_document(document=up_path,
                                                                 quote=True,
                                                                 thumb=thumb,
                                                                 caption=cap_mono,
                                                                 disable_notification=True,
                                                                 progress=self.__upload_progress)
            self.__sent_msg = self.__sent_msg.copy(DUMP_CHAT)

        except FloodWait as f:
            LOGGER.warning(str(f))
            sleep(f.value)
        except RPCError as e:
            LOGGER.error(f"RPCError: {e} Path: {up_path}")
            self.__corrupted += 1
            self.__is_corrupted = True
        except Exception as err:
            LOGGER.error(f"{err} Path: {up_path}")
            self.__corrupted += 1
            self.__is_corrupted = True
        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
            osremove(thumb)
        if not self.__is_cancelled and \
                   (not self.__listener.seed or self.__listener.newDir or dirpath.endswith("splited_files_mltb")):
            try:
                osremove(up_path)
            except:
                pass

    def __upload_progress(self, current, total):
        if self.__is_cancelled:
            app.stop_transmission()
            return
        with self.__resource_lock:
            chunk_size = current - self._last_uploaded
            self._last_uploaded = current
            self.uploaded_bytes += chunk_size

    def __user_settings(self):
        if self.__listener.from_user.id in AS_DOC_USERS:
            self.__as_doc = True
        elif self.__listener.from_user.id in AS_MEDIA_USERS:
            self.__as_doc = False
        if not ospath.lexists(self.__thumb):
            self.__thumb = None
           
    def __msg_to_reply(self):
        """
        if DUMP_CHAT is not None:
            if self.__listener.isPrivate:
                msg = self.__listener.message.text
            else:
                msg = self.__listener.message.link
            self.__sent_msg = app.send_message(DUMP_CHAT, msg)
        else:
        """
        self.__sent_msg = app.get_messages(self.__listener.message.chat.id, self.__listener.uid)
    
    @property
    def speed(self):
        with self.__resource_lock:
            try:
                return self.uploaded_bytes / (time() - self.__start_time)
            except:
                return 0

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
        self.__listener.onUploadError('your upload has been stopped!')
