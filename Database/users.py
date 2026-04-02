import secrets


class UsersCache:
    def __init__(self, app):
        self.app = app
        self.cache = {}

    def init_table(self):
        conn, cursor = self.app.get_cursor()
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(255) NOT NULL,
                mail VARCHAR(255) NOT NULL UNIQUE,
                phone VARCHAR(20) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                date_of_birth VARCHAR(10),
                avatar_id VARCHAR(255),
                api_token VARCHAR(255) NOT NULL UNIQUE
                
            )
            """)
            users = self.get_users()
            for u in users: 
                self.cache[u["id"]] = UserManager(u["id"], u, self)
            return self
        finally:
            cursor.close()
            conn.close()


    def create_user(self, data: dict):
        api_token = secrets.token_hex(32)
        data["api_token"] = api_token
        conn, cursor = self.app.get_cursor()
        try:
            cursor.execute(
            "INSERT INTO users (username, mail, phone, password_hash, date_of_birth, api_token) VALUES (%s, %s, %s, %s, %s, %s);",
            (data["username"], data["mail"], data.get("phone", None), data["password_hash"], data["date_of_birth"], api_token)
            )
            user_id = cursor.lastrowid
            self.cache[user_id] = UserManager(user_id, data, self)
            self.app.conversations_cache.add_user(user_id)
            self.app.relationships_cache.add_user(user_id)
            self.app.users_profile_cache.get_or_create(user_id)
            return self.cache[user_id]
        finally: 
            cursor.close()
            conn.close()

    def delete_user(self, user_id:  int):
        conn, cursor = self.app.get_cursor()
        try:
            cursor.execute("DELETE FROM users WHERE id = %s;", (user_id,))
            if user_id in self.cache:
                del self.cache[user_id]
        finally:
            cursor.close()
            conn.close()
            
    def get_users(self):
        conn, cursor = self.app.get_cursor()
        try:
            cursor.execute("SELECT * FROM users;")
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_user_by_token(self, api_token: str):
        for user in self.cache.values():
            if user.get("api_token") == api_token:
                return user
        return None


    


class UserManager:
    def __init__(self, user_id: int, data: dict, cache: UsersCache):
        self.user_id = user_id
        self.data = data
        self.cache = cache
        self.data["dirty"] = False

    def get(self, key: str):
        return self.data.get(key, None)

    def set(self, key: str, value: any):
        self.data[key] = value
        self.data["dirty"] = True
        return self
    def save(self):
        if not self.data.get("dirty"):
            return
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                UPDATE users
                SET username=%s,
                    mail=%s,
                    phone=%s,
                    password_hash=%s,
                    date_of_birth=%s,
                    api_token=%s,
                    avatar_id=%s
                WHERE id=%s;
            """, (
                self.data["username"],
                self.data["mail"],
                self.data.get("phone", None),
                self.data["password_hash"],
                self.data["date_of_birth"],
                self.data["api_token"],
                self.data.get("avatar_id", None),
                self.user_id
            ))
            self.data["dirty"] = False
        finally:
            cursor.close()
            conn.close()