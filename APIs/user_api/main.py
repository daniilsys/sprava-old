from pydantic import BaseModel
from fastapi import HTTPException, Header, UploadFile, File
from typing import Optional, Literal
import bcrypt
from pathlib import Path
import uuid

class UserInfoDatas(BaseModel):
    user_id: int

class UserBatchInfoDatas(BaseModel):
    user_id: list[int]

class FriendRequestDatas(BaseModel):
    receiver_id: Optional[int] = None
    sender_id: Optional[int] = None
    friend_id: Optional[int] = None

class UserUpdateDatas(BaseModel):
    username: Optional[str] = None
    mail: Optional[str] = None
    date_of_birth: Optional[str] = None
    password: Optional[str] = None

Visibility = Literal['nobody', 'friends', 'everyone']

class UserProfileUpdateDatas(BaseModel):
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    share_location: Optional[Visibility] = None
    share_mail: Optional[Visibility] = None
    share_phone: Optional[Visibility] = None
    share_date_of_birth: Optional[Visibility] = None

class UserProfileInfoDatas(BaseModel):
    user_id: int
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    share_location: Visibility
    share_mail: Visibility
    share_phone: Visibility
    share_date_of_birth: Visibility

class UserAPI:
    def __init__(self, app):
        self.app = app
        self.get_user()
        self.get_me()
        self.get_user_batch()
        self.get_user_from_username()
        
        self.change_username()
        self.change_password()
        self.change_date_of_birth()
        self.change_mail()
        self.change_avatar()

        self.get_user_profile()
        self.get_me_profile()
        self.update_user_profile()

        self.get_friends()
        self.remove_friend()

        self.get_friend_requests()
        self.send_friend_request()
        self.get_sent_friend_requests()
        self.accept_friend_request()
        self.reject_friend_request()
        self.cancel_friend_request()

        self.get_blocked_users()
        self.block_user()
        self.unblock_user()

    def __get_user_from_token(self, authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="No authorization header given")
        
        user = self.app.users_cache.get_user_by_token(authorization)
        if not user: 
            raise HTTPException(status_code=401, detail="No user found with this token")
        
        return user
    
    

    def get_me(self):
        @self.app.get("/me", tags=["User Info"], description="Retrieve your user information.")
        def root(authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            user_profile = self.app.users_profile_cache.get_or_create(user.user_id)
            return {
                "status_code": 200,
                "user_id": user.user_id,
                "username": user.get("username"),
                "mail": user.get("mail"),
                "phone": user.get("phone"),
                "date_of_birth": user.get("date_of_birth"),
                "avatar_id": user.get("avatar_id")
            }
    
    def get_user(self):
        @self.app.get("/user", tags=["User Info"], description="Retrieve user information by user ID.")
        def root(user_id:  int, authorization: str = Header(None)):
            self.__get_user_from_token(authorization)
            
            if user_id not in self.app.users_cache.cache:
                return {
                    "status_code": 404,
                    "message": "The given user_id is not related to any users."
                }
            user = self.app.users_cache.cache[user_id]
            are_friends = self.app.relationships_cache.are_friends(user.user_id, user_id)
            user_profile = self.app.users_profile_cache.get_or_create(user.user_id)
            is_self = user.user_id == user_id
            return {
                "status_code": 200,
                "user_id": user.user_id,
                "username": user.get("username"),
                "mail": user.get("mail") if (is_self or self._can_see(user_profile.get("share_mail"), are_friends)) else None,
                "phone": user.get("phone") if (is_self or self._can_see(user_profile.get("share_phone"), are_friends)) else None,
                "date_of_birth": user.get("date_of_birth") if (is_self or self._can_see(user_profile.get("share_date_of_birth"), are_friends)) else None,
                "avatar_id": user.get("avatar_id")
            }
        
    def get_user_from_username(self):
        @self.app.get("/user/username", tags=["User Info"], description="Retrieve user information by username.")
        def root(username: str, authorization: str = Header(None)):
            self.__get_user_from_token(authorization)

            for user in self.app.users_cache.cache.values():
                if user.get("username").lower() == username.lower():
                    user_profile = self.app.users_profile_cache.get_or_create(user.user_id)
                    are_friends = self.app.relationships_cache.are_friends(user.user_id, user.user_id)
                    is_self = user.user_id == user.user_id
                    return {
                        "status_code": 200,
                        "user_id": user.user_id,
                        "username": user.get("username"),
                        "mail": user.get("mail") if (is_self or self._can_see(user_profile.get("share_mail"), are_friends)) else None,
                        "phone": user.get("phone") if (is_self or self._can_see(user_profile.get("share_phone"), are_friends)) else None,
                        "date_of_birth": user.get("date_of_birth") if (is_self or self._can_see(user_profile.get("share_date_of_birth"), are_friends)) else None,
                        "avatar_id": user.get("avatar_id")
                    }
            return {
                "status_code": 404,
                "message": "The given username is not related to any users."
            }
    def get_user_batch(self):
        @self.app.post("/user/batch", tags=["User Info"], description="Retrieve user information for a batch of user IDs.")
        def root(data: UserBatchInfoDatas, authorization: str = Header(None)):
            self.__get_user_from_token(authorization)

            user_ids = data.user_id
            users_info = []

            for uid in user_ids:
                if uid in self.app.users_cache.cache:
                    user = self.app.users_cache.cache[uid]
                    user_profile = self.app.users_profile_cache.get_or_create(user.user_id)
                    are_friends = self.app.relationships_cache.are_friends(user.user_id, uid)
                    is_self = user.user_id == uid
                    users_info.append({
                        "user_id": user.user_id,
                        "username": user.get("username"),
                        "mail": user.get("mail") if (is_self or self._can_see(user_profile.get("share_mail"), are_friends)) else None,
                        "phone": user.get("phone") if (is_self or self._can_see(user_profile.get("share_phone"), are_friends)) else None,
                        "date_of_birth": user.get("date_of_birth") if (is_self or self._can_see(user_profile.get("share_date_of_birth"), are_friends)) else None,
                        "avatar_id": user.get("avatar_id")
                    })

            return {
                "status_code":  200,
                "users":  users_info
            }
    
    def get_user_profile(self):
        @self.app.get("/user/profile", tags=["User Profile"], description="Retrieve user profile information by user ID.")
        def root(user_id: int, authorization: str = Header(None)):
            requester = self.__get_user_from_token(authorization)

            if user_id not in self.app.users_cache.cache:
                raise HTTPException(status_code=404, detail="User not found")

            if self.app.relationships_cache.are_blocked(user_id, requester.user_id):
                raise HTTPException(status_code=403, detail="You are blocked by this user.")

            user = self.app.users_cache.cache[user_id]
            profile = self.app.users_profile_cache.get_or_create(user_id)

            is_self = requester.user_id == user_id
            are_friends = self.app.relationships_cache.are_friends(requester.user_id, user_id)

            share_location = profile.get("share_location") or "nobody"
            share_phone = profile.get("share_phone") or "nobody"
            share_mail = profile.get("share_mail") or "nobody"
            share_dob = profile.get("share_date_of_birth") or "nobody"

            return {
                "status_code": 200,
                "user_id": user_id,
                "bio": profile.get("bio"),
                "website": profile.get("website"),

                "location": profile.get("location") if (is_self or self._can_see(share_location, are_friends)) else None,
                "phone": user.get("phone") if (is_self or self._can_see(share_phone, are_friends)) else None,
                "mail": user.get("mail") if (is_self or self._can_see(share_mail, are_friends)) else None,
                "date_of_birth": user.get("date_of_birth") if (is_self or self._can_see(share_dob, are_friends)) else None,
            }
    
    def get_me_profile(self):
        @self.app.get("/me/profile", tags=["User Profile"], description="Retrieve your user profile information.")
        def root(authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            profile = self.app.users_profile_cache.get_or_create(user.user_id)

            return {
                "status_code": 200,
                "user_id": user.user_id,
                "bio": profile.get("bio"),
                "location": profile.get("location"),
                "website": profile.get("website"),
                "share_location": profile.get("share_location") or "nobody",
                "share_mail": profile.get("share_mail") or "nobody",
                "share_phone": profile.get("share_phone") or "nobody",
                "share_date_of_birth": profile.get("share_date_of_birth") or "nobody"
            }
            

    def change_username(self):
        @self.app.post("/me/change_username", tags=["User Info"], description="Change your username.")
        def root(data: UserUpdateDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            username = data.username

            user.set("username", username)
            user.save()
            return {
                "status_code": 200,
                "message": "Username updated.",
                "user_id": user.user_id,
                "new_username": username
            }
    def change_password(self):
        @self.app.post("/me/change_password", tags=["User Info"], description="Change your password.")
        def root(data: UserUpdateDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            password_hash = bcrypt.hashpw(
                data.password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")
            user.set("password_hash", password_hash)
            user.save()
            return {
                "status_code": 200,
                "message": "Password updated.",
                "user_id": user.user_id
            }
        
    def change_date_of_birth(self):
        @self.app.post("/me/change_date_of_birth", tags=["User Info"], description="Change your date of birth.")
        def root(data: UserUpdateDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            date_of_birth = data.date_of_birth
            user.set("date_of_birth", date_of_birth)
            user.save()
            return {
                "status_code": 200,
                "message": "Date of birth updated.",
                "user_id": user.user_id,
                "new_date_of_birth": date_of_birth
            }
        
    def change_mail(self):
        @self.app.post("/me/change_mail", tags=["User Info"], description="Change your email address.")
        def root(data: UserUpdateDatas, authorization: str = Header(None)):
            mail = data.mail
            user = self.__get_user_from_token(authorization)
            user.set("mail", mail)
            user.save()
            return {
                "status_code": 200,
                "message": "Mail updated.",
                "user_id": user.user_id,
                "new_mail": mail
            }
        
    def change_avatar(self):
        @self.app.post("/me/change_avatar", tags=["User Info"], description="Change your avatar.")
        async def root(file: UploadFile = File(...), authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            ext = Path(file.filename).suffix
            if ext.lower() not in [".jpg", ".jpeg", ".png", ".gif"]:
                return {
                    "status_code": 400,
                    "message": "Invalid file type. Only .jpg, .jpeg, .png, .gif are allowed."
                }
            
            contents = await file.read()
            file_size = len(contents) / (1024 * 1024)
            if file_size > 5:
                return {
                    "status_code": 413,
                    "message": "File size exceeds the maximum limit of 5 MB."
                }
            id = uuid.uuid4()
            filename = f"{id}{ext}"
            self.app.medias.save_avatar(filename, contents)

            user.set("avatar_id", f"{id}{ext}")
            user.save()

            return {
                "status_code": 200,
                "message": "Avatar updated.",
                "user_id": user.user_id,
                "avatar_id": id
            }
    
    def update_user_profile(self):
        @self.app.post("/me/update_profile", tags=["User Profile"], description="Update your user profile.")
        def root(data: UserProfileUpdateDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)
            profile = self.app.users_profile_cache.get_or_create(user.user_id)

            if data.bio is not None:
                profile.set("bio", data.bio)
            if data.location is not None:
                profile.set("location", data.location)
            if data.website is not None:
                profile.set("website", data.website)
            if data.share_location is not None:
                profile.set("share_location", data.share_location)
            if data.share_mail is not None:
                profile.set("share_mail", data.share_mail)
            if data.share_phone is not None:
                profile.set("share_phone", data.share_phone)
            if data.share_date_of_birth is not None:
                profile.set("share_date_of_birth", data.share_date_of_birth)

            profile.save()

            return {
                "status_code": 200,
                "message": "User profile updated.",
                "user_id": user.user_id
            }

    def get_friends(self):
        @self.app.get("/me/friends", tags=["Friends"], description="Retrieve a list of your friend's user IDs.")
        def root(authorization:  str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship = self.app.relationships_cache.cache[user.user_id]["friends"]
            return {
                "status_code": 200,
                "friends_ids": relationship.get_friends()
            }

    def remove_friend(self):
        @self.app.delete("/me/remove_friend", tags=["Friends"], description="Remove a friend from your friends list.")
        def root(data: FriendRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship = self.app.relationships_cache.cache[user.user_id]["friends"]

            if data.friend_id not in self.app.users_cache.cache:
                return {
                    "status_code":  404,
                    "message": "The given friend_id is not related to any users."
                }

            friends = relationship.get_friends()
            if data.friend_id not in friends: 
                return {
                    "status_code": 404,
                    "message": "You are not friends with this user."
                }

            relationship.remove_friend(data.friend_id)

            return {
                "status_code": 200,
                "message": "Friend removed.",
                "user_id": user.user_id,
                "removed_friend_id": data.friend_id
            }

    def get_friend_requests(self):
        @self.app.get("/me/friend_requests", tags=["Friends Requests"], description="Retrieve a list of your received friend request IDs.")
        def root(authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship = self.app.relationships_cache.cache[user.user_id]["requests"]
            return {
                "status_code": 200,
                "friend_requests_ids": relationship.get_received_requests()
            }
        
    def get_sent_friend_requests(self):
        @self.app.get("/me/sent_friend_requests", tags=["Friends Requests"], description="Retrieve a list of your sent friend request IDs.")
        def root(authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship = self.app.relationships_cache.cache[user.user_id]["requests"]
            return {
                "status_code": 200,
                "sent_friend_requests_ids": relationship.get_sent_requests()
            }
        

    def send_friend_request(self):
        @self.app.post("/me/send_friend_request", tags=["Friends Requests"], description="Send a friend request to another user.")
        async def root(data: FriendRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship = self.app.relationships_cache.cache[user.user_id]["requests"]

            if data.receiver_id not in self.app.users_cache.cache:
                return {
                    "status_code":  404,
                    "message": "The given receiver_id is not related to any users."
                }

            if data.receiver_id == user.user_id:
                return {
                    "status_code":  400,
                    "message": "You cannot send a friend request to yourself."
                }

            if relationship.has_pending_request(data.receiver_id):
                return {
                    "status_code": 409,
                    "message": "A friend request already exists between these users."
                }

            friends = self.app.relationships_cache.cache[user.user_id]["friends"]
            if data.receiver_id in friends.get_friends():
                return {
                    "status_code": 409,
                    "message": "You are already friends with this user."
                }

            relationship.send_request(data.receiver_id)

            await self.app.websocket_managers.send_personal_message(data.receiver_id, {
                "type": "new_friend_request",
                "sender_id": user.user_id,
                "sender_username": user.get("username")
            })

            return {
                "status_code":  200,
                "message":  "Friend request sent.",
                "user_id": user.user_id,
                "receiver_id": data.receiver_id
            }

    def cancel_friend_request(self):
        @self.app.delete("/me/cancel_friend_request", tags=["Friends Requests"], description="Cancel a sent friend request.")
        def root(data: FriendRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship = self.app.relationships_cache.cache[user.user_id]["requests"]

            if data.receiver_id not in self.app.users_cache.cache:
                return {
                    "status_code":  404,
                    "message": "The given receiver_id is not related to any users."
                }

            if not relationship.has_pending_request(data.receiver_id):
                return {
                    "status_code": 404,
                    "message":  "No pending friend request exists between these users."
                }

            relationship.cancel_request(data.receiver_id)

            return {
                "status_code": 200,
                "message": "Friend request canceled.",
                "user_id": user.user_id,
                "receiver_id": data.receiver_id
            }

    def accept_friend_request(self):
        @self.app.post("/me/accept_friend_request", tags=["Friends Requests"], description="Accept a received friend request.")
        async def root(data: FriendRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship_requests = self.app.relationships_cache.cache[user.user_id]["requests"]
            
            if data.sender_id not in self.app.users_cache.cache:
                return {
                    "status_code":  404,
                    "message": "The given sender_id is not related to any users."
                }

            if not relationship_requests.has_pending_request(data.sender_id):
                return {
                    "status_code": 404,
                    "message": "No pending friend request exists between these users."
                }

            relationship_requests.accept_request(data.sender_id)
            await self.app.websocket_managers.send_personal_message(data.sender_id, {
                "type": "friend_request_accepted",
                "friend_id": user.user_id,
                "friend_username": user.get("username")
            })

            return {
                "status_code": 200,
                "message": "Friend request accepted.",
                "user_id": user.user_id,
                "new_friend_id": data.sender_id
            }

    def reject_friend_request(self):
        @self.app.delete("/me/reject_friend_request", tags=["Friends Requests"], description="Reject a received friend request.")
        def root(data: FriendRequestDatas, authorization:  str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship_requests = self.app.relationships_cache.cache[user.user_id]["requests"]

            if data.sender_id not in self.app.users_cache.cache:
                return {
                    "status_code": 404,
                    "message": "The given sender_id is not related to any users."
                }

            if not relationship_requests.has_pending_request(data.sender_id):
                return {
                    "status_code": 404,
                    "message":  "No pending friend request exists between these users."
                }

            relationship_requests.reject_request(data.sender_id)

            return {
                "status_code":  200,
                "message":  "Friend request rejected.",
                "user_id": user.user_id,
                "rejected_friend_id": data.sender_id
            }

    def get_blocked_users(self):
        @self.app.get("/me/blocked_users", tags=["Blocked Users"], description="Retrieve a list of your blocked user IDs.")
        def root(authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship_blocked = self.app.relationships_cache.cache[user.user_id]["blocked"]
            return {
                "status_code": 200,
                "blocked_users_ids":  relationship_blocked.get_blocked_users()
            }

    def block_user(self):
        @self.app.post("/me/block_user", tags=["Blocked Users"], description="Block a user.")
        def root(data: FriendRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship_blocked = self.app.relationships_cache.cache[user.user_id]["blocked"]
            
            if data.friend_id not in self.app.users_cache.cache:
                return {
                    "status_code": 404,
                    "message": "The given user_id is not related to any users."
                }

            if data.friend_id in relationship_blocked.get_blocked_users():
                return {
                    "status_code": 409,
                    "message": "User is already blocked."
                }

            relationship_blocked.block_user(data.friend_id)

            return {
                "status_code": 200,
                "message": "User blocked.",
                "user_id": user.user_id,
                "blocked_user_id":  data.friend_id
            }

    def unblock_user(self):
        @self.app.delete("/me/unblock_user", tags=["Blocked Users"], description="Unblock a user.")
        def root(data:  FriendRequestDatas, authorization: str = Header(None)):
            user = self.__get_user_from_token(authorization)

            relationship_blocked = self.app.relationships_cache.cache[user.user_id]["blocked"]

            if data.friend_id not in self.app.users_cache.cache:
                return {
                    "status_code": 404,
                    "message":  "The given user_id is not related to any users."
                }

            relationship_blocked.unblock_user(data.friend_id)

            return {
                "status_code": 200,
                "message": "User unblocked.",
                "user_id": user.user_id,
                "unblocked_user_id": data.friend_id
            }