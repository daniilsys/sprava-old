# Socket.IO API

## Connection

- **URL:** `http://<host>:8000/socket.io/`
- **Transport:** Socket.IO (WebSocket avec fallback polling)
- **Authentification:** Token passé via le paramètre `auth` à la connexion.

```js
const socket = io("http://localhost:8000", {
  auth: { token: "votre_api_token" }
});
```

Si le token est invalide ou manquant, la connexion est refusée avec une erreur `ConnectionRefusedError`.

### Comportement à la connexion

1. Le serveur vérifie le token
2. Associe le `sid` Socket.IO à l'utilisateur (supporte plusieurs connexions par utilisateur)
3. Notifie tous ses amis connectés via `friend_status_change` → `"online"`

### Comportement à la déconnexion

1. Retire le `sid` de la liste des connexions actives
2. Si c'était la dernière connexion de l'utilisateur, notifie tous ses amis connectés via `friend_status_change` → `"offline"`

---

## Events Client → Serveur

### `send_message`
Envoie un message à un utilisateur. Le message est envoyé aux deux participants.
```js
socket.emit("send_message", { receiver_id: 2, content: "Bonjour !" });
```

### `typing`
Notifie le destinataire que l'expéditeur est en train d'écrire.
```js
socket.emit("typing", { receiver_id: 2 });
```

### `stop_typing`
Notifie le destinataire que l'expéditeur a arrêté d'écrire.
```js
socket.emit("stop_typing", { receiver_id: 2 });
```

### `mark_read`
Marque la conversation comme lue et notifie l'autre participant.
```js
socket.emit("mark_read", { conversation_id: 10 });
```

### `get_online_friends`
Demande la liste des amis actuellement en ligne.
```js
socket.emit("get_online_friends", {});
```

---

## Events Serveur → Client

### Presence et frappe

#### `friend_status_change`
Notifie un changement de statut en ligne/hors ligne d'un ami.
```json
{
  "user_id": 2,
  "status": "online"
}
```
| Champ | Type | Description |
| --- | --- | --- |
| `user_id` | int | ID de l'ami dont le statut a change |
| `status` | string | `"online"` ou `"offline"` |

#### `user_typing`
Notifie qu'un utilisateur est en train d'ecrire ou a arrete.
```json
{
  "user_id": 2,
  "is_typing": true
}
```
| Champ | Type | Description |
| --- | --- | --- |
| `user_id` | int | ID de l'utilisateur qui ecrit |
| `is_typing` | boolean | `true` si en train d'ecrire, `false` sinon |

#### `online_friends`
Reponse a la demande `get_online_friends`.
```json
{
  "friends": [2, 3, 5]
}
```
| Champ | Type | Description |
| --- | --- | --- |
| `friends` | int[] | Liste des IDs des amis actuellement en ligne |

---

### Messages de chat

#### `new_message`

**Via Socket.IO `send_message` :**
Envoyé aux deux participants.
```json
{
  "message_id": 123,
  "sender_id": 1,
  "receiver_id": 2,
  "content": "Bonjour !",
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

**Via REST `/conversation/send_message` :**
Envoyé aux deux participants (expéditeur inclus pour sync multi-device).
```json
{
  "conversation_id": 10,
  "message_id": 456,
  "sender_id": 1,
  "content": "Bonjour !",
  "created_at": "2024-01-01T12:00:00.000000",
  "media_ids": []
}
```

| Champ | Type | Description |
| --- | --- | --- |
| `conversation_id` | int | ID de la conversation |
| `message_id` | int | ID du message cree |
| `sender_id` | int | ID de l'expediteur |
| `content` | string | Contenu du message |
| `created_at` / `timestamp` | string | Date et heure ISO 8601 |
| `media_ids` | int[] | Liste des IDs de medias attaches (REST uniquement) |

#### `delete_message`
Un message a ete supprime. Envoyé aux deux participants.
```json
{
  "message_id": 456
}
```

#### `messages_read`
Les messages d'une conversation ont ete marques comme lus.
```json
{
  "conversation_id": 10,
  "user_id": 1
}
```

---

### Conversations

#### `new_conversation`
Une nouvelle conversation a ete creee (via REST `/create_conversation`). Envoyé à l'autre participant.
```json
{
  "conversation_id": 10,
  "other_user_id": 2
}
```

#### `conversation_deleted`
Une conversation a ete supprimee (via REST `/delete_conversation`). Envoyé à l'autre participant.
```json
{
  "conversation_id": 10
}
```

---

### Relations

#### `new_friend_request`
Une demande d'ami a ete recue (via REST `/me/send_friend_request`).
```json
{
  "sender_id": 1,
  "sender_username": "alice"
}
```

#### `friend_request_accepted`
Une demande d'ami a ete acceptee (via REST `/me/accept_friend_request`).
```json
{
  "friend_id": 2,
  "friend_username": "bob"
}
```

#### `friend_request_rejected`
Une demande d'ami a ete rejetee (via REST `/me/reject_friend_request`).
```json
{
  "user_id": 2,
  "username": "bob"
}
```

#### `friend_request_canceled`
Une demande d'ami envoyee a ete annulee (via REST `/me/cancel_friend_request`).
```json
{
  "sender_id": 1
}
```

#### `friend_removed`
Un ami a ete supprime de la liste d'amis (via REST `/me/remove_friend`).
```json
{
  "user_id": 1,
  "username": "alice"
}
```

---

### Utilisateurs

#### `user_updated`
Un ami a mis a jour son profil (username ou avatar). Envoyé à tous les amis.
```json
{
  "user_id": 1,
  "username": "alice_new",
  "avatar_id": "abc-123.png"
}
```

#### `user_blocked`
Vous avez ete bloque par un utilisateur (via REST `/me/block_user`).
```json
{
  "user_id": 1
}
```

#### `user_unblocked`
Vous avez ete debloque par un utilisateur (via REST `/me/unblock_user`).
```json
{
  "user_id": 1
}
```

---

## Architecture technique

### ConnectionManager

Le `ConnectionManager` gere les connexions Socket.IO actives :

- **Connexions multiples:** Un utilisateur peut avoir plusieurs connexions simultanees (plusieurs appareils/onglets)
- **Mapping sid ↔ user_id:** Chaque `sid` Socket.IO est associe a un `user_id`
- **Detection hors ligne:** Un utilisateur est considere hors ligne uniquement quand toutes ses connexions sont fermees

### Methodes disponibles

| Methode | Description |
| --- | --- |
| `register(sid, user_id)` | Associe un sid a un utilisateur |
| `unregister(sid)` | Retire un sid et retourne le user_id |
| `get_user_id(sid)` | Retourne le user_id associe a un sid |
| `emit_to_user(user_id, event, data)` | Emet un event a toutes les connexions d'un utilisateur |
| `emit_to_multiple(user_ids, event, data, exclude)` | Emet a plusieurs utilisateurs |
| `emit_to_conversation(event, data, user1_id, user2_id)` | Emet aux deux participants d'une conversation |
| `is_user_online(user_id)` | Verifie si un utilisateur a au moins une connexion active |
| `get_online_users()` | Retourne la liste des utilisateurs connectes |

### Migration depuis WebSocket natif

Le passage de WebSocket natif a Socket.IO apporte :

- **Reconnexion automatique** cote client
- **Fallback polling** si WebSocket n'est pas disponible
- **Events nommes** au lieu du dispatch JSON manuel par `type`
- **Authentification structurée** via le parametre `auth` au lieu du token dans l'URL
