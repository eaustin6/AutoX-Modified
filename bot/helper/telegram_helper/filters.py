from telegram.ext import MessageFilter
from telegram import Message
from bot import AUTHORIZED_CHATS, SUDO_USERS, OWNER_ID, LOGGER
from bot.helper.ext_utils.bot_utils import is_magnet, is_url

class CustomFilters:
    class _OwnerFilter(MessageFilter):
        def filter(self, message):
            return bool(message.from_user.id == OWNER_ID)

    owner_filter = _OwnerFilter()

    class _AuthorizedUserFilter(MessageFilter):
        def filter(self, message):
            id = message.from_user.id
            return bool(id in AUTHORIZED_CHATS or id in SUDO_USERS or id == OWNER_ID)

    authorized_user = _AuthorizedUserFilter()

    class _AuthorizedChat(MessageFilter):
        def filter(self, message):
            return bool(message.chat.id in AUTHORIZED_CHATS)

    authorized_chat = _AuthorizedChat()

    class _SudoUser(MessageFilter):
        def filter(self, message):
            return bool(message.from_user.id in SUDO_USERS)

    sudo_user = _SudoUser()

    class _MirrorOwner(MessageFilter):
        def filter(self, message: Message):
            user_id = message.from_user.id
            if user_id == OWNER_ID:
                return True
            args = str(message.text).split(' ')
            if len(args) > 1:
                # Cancelling by gid
                with download_dict_lock:
                    for message_id, status in download_dict.items():
                        if status.gid() == args[1] and status.message.from_user.id == user_id:
                            return True
                    else:
                        return False
            elif not message.reply_to_message:
                return True
            # Cancelling by replying to original mirror message
            reply_user = message.reply_to_message.from_user.id
            return bool(reply_user == user_id)
    mirror_owner_filter = _MirrorOwner()


    class _MirrorTorrentsAndMagnets(MessageFilter):
        def filter(self, message: Message):
            
            if message.edit_date:
                LOGGER.info("Edited msg")
                return

            if message.document and '.torrent' in message.document.file_name:
                a = True
            elif message.text and is_magnet(message.text):
                a = True
            else:
                return False

            if message.chat.id in AUTHORIZED_CHATS:
                b = True
            elif message.chat.type != "channel":
                if message.from_user.id in (AUTHORIZED_CHATS, SUDO_USERS):
                    b =  True
                elif message.from_user.id == OWNER_ID:
                    b = True
                else:
                    return False
            else:
                return False
            return a and b

    mirror_torrent_and_magnets = _MirrorTorrentsAndMagnets()

    class _MirrorURI(MessageFilter):
        def filter(self, message: Message):
            
            if message.edit_date:
                LOGGER.info("Edited msg")
                return
            if message.text and is_url(message.text):
                a = True
            else:
                return False

            if message.chat.id in AUTHORIZED_CHATS:
                b = True
            elif message.chat.type != "channel":
                if message.from_user.id in (AUTHORIZED_CHATS, SUDO_USERS):
                    b =  True
                elif message.from_user.id == OWNER_ID:
                    b = True
                else:
                    return False
            else:
                return False
            return a and b

    mirror_uris = _MirrorURI()

    @staticmethod
    def _owner_query(user_id):
        return user_id == OWNER_ID or user_id in SUDO_USERS
