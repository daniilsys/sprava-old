from pydantic import BaseModel
from fastapi import HTTPException, Header
from typing import Optional
from datetime import datetime

class ConversationCreationDatas(BaseModel):
    user2_id: int

class ConversationRequestDatas(BaseModel):
    conversation_id: int

class ConversationMessageRequestDatas(BaseModel):
    conversation_id: int
    limit: int = 50
    offset: int = 0

class ConversationMessageDeleteDatas(BaseModel):
    message_id: int


class ConversationMessageSendDatas(BaseModel):
    conversation_id:  int
    content: str

class ConversationsAPI:
    def __init__(self, app):
        self.app = app
        self.create_conversation()
        self.delete_conversation()
        self.get_conversations()
        self.get_conversation_messages()
        self.conversation_send_message()
        self.conversation_delete_message()
        self.conversation_read()

    def __get_user_from_token(self, authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="No authorization header given")

        user = self.app.users_cache.get_user_by_token(authorization)
        if not user:
            raise HTTPException(status_code=401, detail="No user found with this token")

        return user

    def create_conversation(self):
        @self.app.post("/create_conversation", tags=["Conversations"],
                       description="Create a new conversation with a friend.")
        async def root(data: ConversationCreationDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            if data.user2_id not in self.app.users_cache.cache:
                return {
                    "status_code":  404,
                    "message": "The given user ID does not correspond to any user."
                }
            if not self.app.relationships_cache.are_friends(user.user_id, data.user2_id):
                return {
                    "status_code": 403,
                    "message": "You can only create conversations with your friends."
                }

            if self.app.relationships_cache.are_blocked(user.user_id, data.user2_id):
                return {
                    "status_code": 403,
                    "message": "You cannot create conversations with users you have blocked or who have blocked you."
                }

            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            conversation_id = conversation_manager.get_or_create_conversation(data.user2_id)
            await self.app.websocket_manager.emit_to_user(data.user2_id, "new_conversation", {
                "conversation_id": conversation_id,
                "other_user_id": user.user_id
            })
            return {
                "status_code": 200,
                "conversation_id": conversation_id
            }

    def delete_conversation(self):
        @self.app.delete("/delete_conversation", tags=["Conversations"],
                        description="Delete a conversation.")
        async def root(data: ConversationRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            other_user_id = conversation_manager.get_other_user_id(data.conversation_id)
            conversation_manager.delete_conversation(data.conversation_id)

            await self.app.websocket_manager.emit_to_user(other_user_id, "conversation_deleted", {
                "conversation_id": data.conversation_id
            })
            return {
                "status_code": 200,
                "message": "Conversation deleted successfully."
            }

    def get_conversations(self):
        @self.app.get("/me/conversations", tags=["Conversations"],
                      description="Retrieve a list of your conversations with informations about it, such as last message, unread messages, etc.")
        def root(authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            conversations = conversation_manager.get_conversations()
            return {
                "status_code": 200,
                "conversations": conversations
            }

    def get_conversation_messages(self):
        @self.app.get("/conversation/messages", tags=["Conversations"],
                      description="Retrieve messages from a specific conversation.")
        def root(conversation_id: int, limit: int = 50, offset:  int = 0, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            messages = conversation_manager.get_messages(conversation_id, limit, offset)

            return {
                "status_code": 200,
                "messages": messages
            }

    def conversation_send_message(self):
        @self.app.post("/conversation/send_message", tags=["Conversations"], description="Send a message in a specific conversation.")
        async def root(data: ConversationMessageSendDatas, authorization:  str = Header(None)):
            user = self.__get_user_from_token(authorization)
            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            other_user_id = conversation_manager.get_other_user_id(data.conversation_id)

            if self.app.relationships_cache.are_blocked(user.user_id, other_user_id):
                return {
                    "status_code": 403,
                    "message": "You cannot send messages in conversations with users you have blocked or who have blocked you."
                }

            message_id = conversation_manager.send_message(data.conversation_id, data.content)

            message_data = {
                "conversation_id": data.conversation_id,
                "message_id": message_id,
                "sender_id": user.user_id,
                "content": data.content,
                "created_at": datetime.now().isoformat(),
                "media_ids": []
            }

            await self.app.websocket_manager.emit_to_user(other_user_id, "new_message", message_data)
            await self.app.websocket_manager.emit_to_user(user.user_id, "new_message", message_data)

            return {
                "status_code": 200,
                "message_id": message_id,
                "content": data.content,
                "message": "Message sent successfully."
            }

    def conversation_delete_message(self):
        @self.app.delete("/conversation/delete_message", tags=["Conversations"], description="Delete a message you have sent in a conversation.")
        async def root(data: ConversationMessageDeleteDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            sender_id = conversation_manager.get_sender_id(data.message_id)
            if sender_id != user.user_id:
                return {
                    "status_code": 403,
                    "message": "You can only delete your own messages."
                }

            conversation_id = conversation_manager.get_conversation_id_from_message_id(data.message_id)

            if not conversation_id:
                return {
                    "status_code": 404,
                    "message": "Message not found in any of your conversations."
                }
            conversation_manager.delete_message(data.message_id)
            other_user_id = conversation_manager.get_other_user_id(conversation_id)
            await self.app.websocket_manager.emit_to_user(other_user_id, "delete_message", {
                "message_id": data.message_id
                })
            await self.app.websocket_manager.emit_to_user(user.user_id, "delete_message", {
                "message_id": data.message_id
                })
            return {
                "status_code": 200,
                "deleted_message_id": data.message_id,
                "message": "Message deleted successfully."
            }

    def conversation_read(self):
        @self.app.put("/conversation/read", tags=["Conversations"], description="Mark messages as read in a specific conversation.")
        async def root(data: ConversationRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            conversation_manager = self.app.conversations_cache.cache[user.user_id]
            conversation_manager.mark_as_read(data.conversation_id)

            await self.app.websocket_manager.emit_to_user(conversation_manager.get_other_user_id(data.conversation_id), "messages_read", {
                "conversation_id": data.conversation_id,
            })
            return {
                "status_code": 200,
                "message": "Messages marked as read."
            }
