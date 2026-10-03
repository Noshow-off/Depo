import os
import telepotpro
from telepotpro.exception import TelegramError

JOINED_STATUSES = ('creator', 'administrator', 'member')


def _split(value):
    return [v.strip().strip('"').strip("'") for v in (value or '').split(',') if v.strip()]


def get_channels():
    return _split(os.environ.get('MUST_JOIN'))


def _get_links():
    return _split(os.environ.get('MUST_JOIN_LINK'))


def _normalize(channel):
    """'@name' / 'name' -> '@name', numeric id -> int."""
    channel = channel.strip()
    if channel.lstrip('-').isdigit():
        return int(channel)
    if not channel.startswith('@'):
        channel = '@' + channel
    return channel


def is_member(bot, user_id, channel):
    """True if the user is a member of the channel, False if not.
    Returns None if the check itself fails (e.g. bot is not admin)."""
    try:
        member = bot.getChatMember(_normalize(channel), user_id)
    except TelegramError as e:
        print(f"[must_join] getChatMember failed for {channel}: {e}")
        return None
    except Exception as e:
        print(f"[must_join] unexpected error for {channel}: {e}")
        return None

    status = member.get('status')
    if status in JOINED_STATUSES:
        return True
    # restricted user who is still in the chat
    if status == 'restricted' and member.get('is_member'):
        return True
    return False


def _invite_url(bot, channel, index):
    links = _get_links()
    if index < len(links):
        return links[index]

    ch = _normalize(channel)
    if isinstance(ch, str):
        return 'https://t.me/' + ch.lstrip('@')

    # private channel: if the bot is admin it can generate a link
    try:
        return bot.exportChatInviteLink(ch)
    except Exception as e:
        print(f"[must_join] could not create invite link ({channel}): {e}")
        return None


def check(bot, msg, reply_to=True):
    """
    Return True  -> user is allowed, the bot continues.
    Return False -> user has not joined, a join message has been sent.

    Usage in the bot:
        if not must_join.check(bot, msg):
            return
    """
    channels = get_channels()
    if not channels:
        return True  # feature is off

    user_id = msg['from']['id']
    chat_id = msg['chat']['id']

    not_joined = []
    for i, channel in enumerate(channels):
        joined = is_member(bot, user_id, channel)
        if joined is False:
            not_joined.append((i, channel))
        # joined is None -> check failed (bot not admin etc.), so we don't block the user

    if not not_joined:
        return True

    buttons = []
    for i, channel in not_joined:
        url = _invite_url(bot, channel, i)
        if url:
            buttons.append([{'text': '📢 Join Channel', 'url': url}])

    name = msg['from'].get('first_name', 'User')
    text = (
        f"❌ *Hello {name}!*\n\n"
        "You need to join our channel before you can use this bot.\n"
        "After joining, send your command again. 👇"
    )

    kwargs = {'parse_mode': 'Markdown'}
    if reply_to:
        kwargs['reply_to_message_id'] = msg['message_id']
    if buttons:
        kwargs['reply_markup'] = {'inline_keyboard': buttons}

    try:
        bot.sendMessage(chat_id, text, **kwargs)
    except Exception as e:
        print(f"[must_join] could not send join message: {e}")
    return False
