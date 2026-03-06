import os
import time
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.exceptions import ApiError

# Берём токен и id группы из Secrets
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

if not VK_TOKEN:
    raise RuntimeError("Не найден VK_TOKEN в переменных окружения")

if not VK_GROUP_ID:
    raise RuntimeError("Не найден VK_GROUP_ID в переменных окружения")

try:
    VK_GROUP_ID = int(VK_GROUP_ID)
except ValueError:
    raise RuntimeError("VK_GROUP_ID должен быть числом")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)


def is_clip(video_attachment: dict) -> bool:
    """
    Проверяем, является ли video-вложение клипом.
    Делаем это через video.get и анализируем player/title.
    """
    owner_id = video_attachment.get("owner_id")
    video_id = video_attachment.get("id")
    access_key = video_attachment.get("access_key")

    if owner_id is None or video_id is None:
        return False

    video_ref = f"{owner_id}_{video_id}"
    if access_key:
        video_ref += f"_{access_key}"

    try:
        result = vk.video.get(videos=video_ref)
        items = result.get("items", [])
        if not items:
            return False

        video = items[0]
        player = (video.get("player") or "").lower()
        title = (video.get("title") or "").lower()

        # Основная эвристика: у клипов ссылка плеера обычно содержит /clip
        if "/clip" in player or "vk.com/clip" in player or "vkvideo.ru/clip" in player:
            return True

        # Запасной вариант по названию
        if title.startswith("клип") or title.startswith("clip"):
            return True

        return False

    except ApiError as e:
        print(f"[video.get] API error: {e}")
        return False
    except Exception as e:
        print(f"[video.get] Unexpected error: {e}")
        return False


def delete_message(peer_id: int, conversation_message_id: int):
    """
    В беседе надёжнее удалять по peer_id + cmids.
    """
    try:
        vk.messages.delete(
            peer_id=peer_id,
            cmids=conversation_message_id,
            delete_for_all=1
        )
        print(f"Удалено сообщение: peer_id={peer_id}, cmid={conversation_message_id}")
    except ApiError as e:
        print(f"[messages.delete] API error: {e}")
    except Exception as e:
        print(f"[messages.delete] Unexpected error: {e}")


print("Бот запущен и слушает сообщения...")

for event in longpoll.listen():
    if event.type != VkBotEventType.MESSAGE_NEW:
        continue

    message = event.object.get("message", {})
    peer_id = message.get("peer_id")
    cmid = message.get("conversation_message_id")
    attachments = message.get("attachments", [])

    if not peer_id or not cmid or not attachments:
        continue

    should_delete = False

    for attachment in attachments:
        if attachment.get("type") != "video":
            continue

        video_data = attachment.get("video", {})
        if is_clip(video_data):
            should_delete = True
            break

    if should_delete:
        delete_message(peer_id, cmid)

    # маленькая пауза, чтобы аккуратнее работать с API
    time.sleep(0.3)
