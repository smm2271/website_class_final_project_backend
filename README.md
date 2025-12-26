# Final Project Backend (FastAPI)

本專案為網站課程期末作業之後端，提供使用者註冊/登入、聊天室建立與訊息 WebSocket 推送等功能，搭配前端 `website_class_final_project_frontend` 使用。

## 技術棧
- FastAPI（REST + WebSocket）
- SQLModel / SQLAlchemy 2.x（ORM）
- PostgreSQL（資料庫）
- JWT（身份驗證）
- Uvicorn（ASGI Server）

## 專案結構
- [app.py](app.py): FastAPI 入口與 CORS 設定、路由註冊
- [auth/](auth): JWT 與使用者密碼雜湊工具
	- [auth/user_auth.py](auth/user_auth.py): Token 建立/驗證
	- [auth/user_factory.py](auth/user_factory.py): 使用者建立、密碼驗證
- [database/](database): ORM 模型、資料庫連線與服務
	- [database/models.py](database/models.py): `User`、`ChatRoom`、`Message` 等表
	- [database/database.py](database/database.py): 連線設定與 Session 取得
	- [database/service.py](database/service.py): 讀寫服務（聊天室、訊息、已讀）
- [routes/](routes): API 與 WebSocket 路由
	- [routes/user.py](routes/user.py): 註冊/登入/登出/刷新 token
	- [routes/message.py](routes/message.py): 建立聊天室、查詢聊天室
	- [routes/exts/message_ext.py](routes/exts/message_ext.py): WebSocket ConnectManager

## 先決條件
- 安裝 Conda（或 Miniconda/Anaconda）
- 可連線的 PostgreSQL 資料庫

## 環境設定
1. 建立並啟用 Conda 環境（本專案以 `final_project` 為例）：

```bash
conda create -n final_project python=3.11 -y
conda activate final_project
```

2. 安裝相依套件：

```bash
python -m pip install -r requirements.txt
```

3. 建立 `.env`（可參考 [`.env.example`](.env.example)）：

```dotenv
DB_USER="your_user"
DB_PASSWORD="your_password"
DB_HOST="localhost"
DB_NAME="your_db"
DB_PORT=5432
SECRET_KEY="your_secret_key"
FRONTEND_URL="your_frontend_url"
```

## 初始化資料庫
確保 `.env` 已設定正確後，執行下列指令建立資料表：

```bash
conda run -n final_project python -m database.database
```

成功後將看到「資料庫表格建立完成！」訊息。

## 啟動服務

```bash
conda run -n final_project uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

啟動後可訪問：
- 健康檢查: `GET /`
- OpenAPI Docs: `http://localhost:8000/docs`

## API 說明（摘要）

使用者相關（路徑前綴 `/user`）
- `POST /user/register`: 註冊使用者
	- Request JSON: `{ "user_id": "u1", "username": "User 1", "password": "pass" }`
	- Response: `{ "id": "...", "user_id": "u1", "username": "User 1" }`
- `POST /user/login`: 登入並回傳 `access_token` 與 `refresh_token` Cookie
	- Request JSON: `{ "user_id": "u1", "password": "pass" }`
	- Response: 同上，並在 Cookie 設定 token（`httponly`）
- `POST /user/logout`: 登出（清除 token Cookie）
- `POST /user/refresh-token`: 使用 `refresh_token` 刷新 `access_token`

聊天室相關（路徑前綴 `/message`）
- `POST /message/create_room`: 建立聊天室（需驗證使用者）
	- Request JSON: `{ "room_name": "optional-name" }`
	- Response: `{ "room_id": "..." }`
- `GET /message/get_rooms`: 取得使用者加入的聊天室列表（需驗證使用者）
	- Response: `{ "room_ids": { "room_uuid": "room_name", ... } }`

### 範例：以 Cookie 驗證

```bash
# 登入取得 Cookie
curl -i -X POST http://localhost:8000/user/login \
	-H "Content-Type: application/json" \
	-d '{"user_id":"u1","password":"pass"}'

# 使用 access_token Cookie 呼叫受保護端點
curl -b "access_token=YOUR_TOKEN" http://localhost:8000/message/get_rooms
```

## WebSocket 使用
路徑：`/message/online`

連線時可透過 Cookie 或 `Authorization: Bearer <token>` 進行驗證。

支援動作（送出 JSON）：
- `send_message`: 發送訊息並廣播
	- 範例: `{ "action_type": "send_message", "chatroom_id": "<uuid>", "content": "hello" }`
- `get_message`: 取得訊息（分頁、時間條件）
	- 範例: `{ "action_type": "get_message", "chatroom_id": "<uuid>", "limit": 50 }`
- `mark_room_read`: 標記聊天室已讀
	- 範例: `{ "action_type": "mark_room_read", "chatroom_id": "<uuid>" }`
- `join_room`: 加入聊天室
	- 範例: `{ "action_type": "join_room", "chatroom_id": "<uuid>" }`
- `leave_room`: 離開聊天室
	- 範例: `{ "action_type": "leave_room", "chatroom_id": "<uuid>" }`
- `disconnect`: 主動斷線