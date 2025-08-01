from flask import Flask, request, abort
import os
import json
from datetime import datetime
import gspread
import re

from oauth2client.service_account import ServiceAccountCredentials

# LINE SDK v3
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent as V3TextMessageContent,
    PostbackEvent
)

app = Flask(__name__)

print("Token is:", os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
if os.getenv("LINE_CHANNEL_ACCESS_TOKEN") is None:
    raise Exception("❌ 沒有設定 LINE_CHANNEL_ACCESS_TOKEN！請回 Railway 補上環境變數")

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    print("=== LINE Webhook Debug ===")
    print("X-Line-Signature:", signature)
    print("Request Body:", body)
    
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Webhook Error: {e}")
        abort(400)
    return "OK"


# 工錢計算邏輯
def 寫入GoogleSheet(時間, 代墊人, 代墊單位, 廠商, 商品):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    sheet = client.open_by_key(sheet_id).sheet1
    row = [時間, 代墊人, 代墊單位, 商品, f"NT${int(價錢)}", ""]
    sheet.append_row(row)

# 處理文字訊息事件
@handler.add(MessageEvent, message=V3TextMessageContent)
def handle_message(event):
    user_msg = event.message.text.strip()
    lines = user_msg.splitlines()

    try:
        if len(lines) != 4 or not lines[0].startswith("墊"):
            raise ValueError("❌ 請輸入正確格式，共 4 行：\n墊代墊人\n代墊單位\n商品\n價錢")

        代墊人 = lines[0].replace("墊", "").strip()
        代墊單位 = lines[1].strip()
        商品 = lines[2].strip()
        純數字 = re.sub(r"[^\d.]", "", lines[3])  # 移除 NT$ 或非數字符號
        價錢 = float(純數字)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        寫入GoogleSheet(now, 代墊人, 代墊單位, 商品, 價錢)

        reply_text = (
            f"✅ 已記錄代墊：\n"
            f"🕒 {now}\n"
            f"🙍‍♂️ {代墊人}\n"
            f"🏢 {代墊單位}\n"
            f"📦 {商品}\n"
            f"💰 {價錢} 元"
        )
    except Exception as e:
        print("處理錯誤：", e)
        reply_text = "❌ 請輸入正確格式，共 4 行：\n墊代墊人\n代墊單位\n商品\n價錢"

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
