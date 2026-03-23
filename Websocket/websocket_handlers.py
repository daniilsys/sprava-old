from datetime import datetime


class WebSocketHandlers:
    def __init__(self, app, manager):
        self.app = app
        self.manager = manager

    async def handle_send_message(self, sid, data):
        sender_id = self.manager.get_user_id(sid)
        receiver_id = data.get("receiver_id")
        content = data.get("content")

        if not receiver_id or not content:
            return

        conversation_manager = self.app.conversations_cache.cache[sender_id]
        message_id = conversation_manager.send_message_with_receiver(receiver_id, content)

        message_data = {
            "message_id": message_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }

        await self.manager.emit_to_conversation("new_message", message_data, sender_id, receiver_id)

    async def handle_typing(self, sid, data):
        sender_id = self.manager.get_user_id(sid)
        receiver_id = data.get("receiver_id")
        if not receiver_id:
            return

        await self.manager.emit_to_user(receiver_id, "user_typing", {
            "user_id": sender_id,
            "is_typing": True,
        })

    async def handle_stop_typing(self, sid, data):
        sender_id = self.manager.get_user_id(sid)
        receiver_id = data.get("receiver_id")
        if not receiver_id:
            return

        await self.manager.emit_to_user(receiver_id, "user_typing", {
            "user_id": sender_id,
            "is_typing": False,
        })

    async def handle_mark_read(self, sid, data):
        sender_id = self.manager.get_user_id(sid)
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            return

        conversation_manager = self.app.conversations_cache.cache[sender_id]
        conversation_manager.mark_as_read(conversation_id)

        conn, cursor = self.app.get_cursor()
        try:
            cursor.execute("""
            SELECT user1_id, user2_id
            FROM conversations
            WHERE id = %s
            """, (conversation_id,))

            result = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if not result:
            return

        other_user_id = result['user2_id'] if result['user1_id'] == sender_id else result['user1_id']

        await self.manager.emit_to_user(other_user_id, "messages_read", {
            "conversation_id": conversation_id,
            "user_id": sender_id,
        })

    async def handle_get_online_friends(self, sid, data):
        sender_id = self.manager.get_user_id(sid)
        friends = self.app.relationships_cache.cache[sender_id]["friends"].get_friends()
        online_friends = [f for f in friends if self.manager.is_user_online(f)]

        await self.manager.emit_to_user(sender_id, "online_friends", {
            "friends": online_friends,
        })

    async def notify_status_change(self, user_id, status):
        friends = self.app.relationships_cache.cache[user_id]["friends"].get_friends()
        for friend_id in friends:
            if self.manager.is_user_online(friend_id):
                await self.manager.emit_to_user(friend_id, "friend_status_change", {
                    "user_id": user_id,
                    "status": status,
                })
