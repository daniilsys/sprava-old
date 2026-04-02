class ConversationsCache:
    def __init__(self, app):
        self.app = app
        self.cache = {}

    def init_table(self):
        self.cache = {}
        conn, cursor = self.app.get_cursor()
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user1_id INT,
                user2_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_conversation (user1_id, user2_id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT PRIMARY KEY AUTO_INCREMENT,
                conversation_id INT,
                sender_id INT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """)

            users = self.app.users_cache.get_users()
            for u in users:
                self.cache[u["id"]] = ConversationManager(u["id"], self)
            return self
        finally:
            cursor.close()
            conn.close()


    def add_user(self, user_id):
        if user_id not in self.cache:
            self.cache[user_id] = ConversationManager(user_id, self)


class ConversationManager:
    def __init__(self, user_id, cache):
        self.user_id = user_id
        self.cache = cache

    def get_or_create_conversation(self, other_user_id):
        user1_id = min(self.user_id, other_user_id)
        user2_id = max(self.user_id, other_user_id)

        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT id FROM conversations 
                WHERE user1_id = %s AND user2_id = %s
            """, (user1_id, user2_id))

            result = cursor.fetchone()
            if result:
                return result['id']

            cursor.execute("""
                INSERT INTO conversations (user1_id, user2_id) 
                VALUES (%s, %s)
            """, (user1_id, user2_id))

            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()

    def get_conversations(self):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT 
                    c.id,
                    c.user1_id,
                    c.user2_id,
                    c.created_at,
                    CASE 
                        WHEN c.user1_id = %s THEN c.user2_id 
                        ELSE c.user1_id 
                    END AS other_user_id,
                    (SELECT content FROM messages 
                     WHERE conversation_id = c.id 
                     ORDER BY created_at DESC LIMIT 1) AS last_message,
                    (SELECT created_at FROM messages 
                     WHERE conversation_id = c.id 
                     ORDER BY created_at DESC LIMIT 1) AS last_message_at,
                    (SELECT COUNT(*) FROM messages 
                     WHERE conversation_id = c.id 
                     AND sender_id != %s 
                     AND is_read = FALSE) AS unread_count,
                    (SELECT username FROM users 
                     WHERE id = CASE
                           WHEN c.user1_id = %s THEN c.user2_id 
                         ELSE c.user1_id 
                     END) AS other_username
                FROM conversations c
                WHERE c.user1_id = %s OR c.user2_id = %s
                ORDER BY last_message_at DESC
            """, (self.user_id, self.user_id, self.user_id, self.user_id, self.user_id))

            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def send_message(self, conversation_id, content):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO messages (conversation_id, sender_id, content) 
                VALUES (%s, %s, %s)
            """, (conversation_id, self.user_id, content))

            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()

    def get_messages(self, conversation_id, limit=50, offset=0):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT * FROM conversations 
                WHERE id = %s AND (user1_id = %s OR user2_id = %s)
            """, (conversation_id, self.user_id, self.user_id))

            if not cursor.fetchone():
                return []

            cursor.execute("""
                SELECT 
                    m.id,
                    m.conversation_id,
                    m.sender_id,
                    m.content,
                    m.created_at,
                    m.is_read
                FROM messages m
                WHERE m.conversation_id = %s
                ORDER BY m.created_at DESC
                LIMIT %s OFFSET %s
            """, (conversation_id, limit, offset))

            messages = cursor.fetchall()

            if not messages: 
                return []
            
            message_ids = [msg["id"] for msg in messages]
            
            placeholders = ','.join(['%s'] * len(message_ids))
            cursor.execute(f"""
                SELECT message_id, id
                FROM media
                WHERE message_id IN ({placeholders})
                ORDER BY id DESC
            """, message_ids)
            
            media_results = cursor.fetchall()
            
            media_ids_by_message = {}
            for media in media_results: 
                message_id = media["message_id"]
                media_id = media["id"]
                if message_id not in media_ids_by_message:
                    media_ids_by_message[message_id] = []
                media_ids_by_message[message_id].append(media_id)
            
            for msg in messages:
                msg["media_ids"] = media_ids_by_message.get(msg["id"], [])
            return messages
            
        finally:
            cursor.close()
            conn.close()

    def mark_as_read(self, conversation_id):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                UPDATE messages 
                SET is_read = TRUE 
                WHERE conversation_id = %s 
                AND sender_id != %s 
                AND is_read = FALSE
            """, (conversation_id, self.user_id))
            return self
        finally:
            cursor.close()
            conn.close()

    def delete_message(self, message_id):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                DELETE FROM messages 
                WHERE id = %s AND sender_id = %s
            """, (message_id, self.user_id))
            return self
        finally:
            cursor.close()
            conn.close()

    def delete_conversation(self, conversation_id):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT * FROM conversations 
                WHERE id = %s AND (user1_id = %s OR user2_id = %s)
            """, (conversation_id, self.user_id, self.user_id))

            if cursor.fetchone():
                cursor.execute("""
                    DELETE FROM conversations WHERE id = %s
                """, (conversation_id,))
            return self
        finally:
            cursor.close()
            conn.close()

    def get_other_user_id(self, conversation_id):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT user1_id, user2_id 
                FROM conversations 
                WHERE id = %s
            """, (conversation_id,))

            result = cursor.fetchone()
            if not result:
                return None

            if result['user1_id'] == self.user_id:
                return result['user2_id']
            else:
                return result['user1_id']
        finally:
            cursor.close()
            conn.close()

    def get_conversation_id_from_message_id(self, message_id):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT conversation_id 
                FROM messages 
                WHERE id = %s
            """, (message_id,))

            result = cursor.fetchone()
            if not result:
                return None

            return result['conversation_id']
        finally:
            cursor.close()
            conn.close()

    def get_sender_id(self, message_id):
        conn, cursor = self.cache.app.get_cursor()
        try:
            cursor.execute("""
                SELECT sender_id 
                FROM messages 
                WHERE id = %s
            """, (message_id,))

            result = cursor.fetchone()
            if not result:
                return None

            return result['sender_id']
        finally:
            cursor.close()
            conn.close()