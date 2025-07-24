from flask import Flask, request, abort
import os
import json
from datetime import datetime
import gspread

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
def 寫入GoogleSheet(時間, 品名, 種類 , 廠商, 售價, 重量, 金價, 加工費):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    sheet = client.open_by_key(sheet_id).sheet1
    row = [時間, 品名, 種類, 廠商, 售價, 重量, 金價, 加工費]
    sheet.append_row(row)

# 處理文字訊息事件
@handler.add(MessageEvent, message=V3TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]  # 去除空行與多餘空白
    
    print("解析後的輸入行：", lines)
    
    try:
        if len(lines) != 6:
            raise ValueError(f"❌ 輸入格式應為 6 行，目前為 {len(lines)} 行")

        品名 = lines[0]
        種類 = lines[1]
        廠商 = lines[2]
        售價 = float(lines[3].replace(',', ''))
        重量 = float(lines[4].replace(',', ''))
        金價 = float(lines[5].replace(',', ''))
        加工費 = round(售價 - 重量 * 金價, 2)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        寫入GoogleSheet(now, 品名, 種類, 廠商, 售價, 重量, 金價, 加工費)

        reply_text = (
            f"✅ 已寫入報表：\n\n"
            f"🕒 時間：{now}\n"
            f"📦 品名：{品名}\n"
            f"🔢 種類：{種類}\n"
            f"🏪 廠商：{廠商}\n"
            f"💰 售價：{售價}\n"
            f"⚖️ 重量：{重量} 錢\n"
            f"📈 金價：{金價} 元/錢\n"
            f"🔧 加工費：{加工費:.2f} 元"
        )
    except Exception as e:
        print("處理失敗：", e)
        reply_text = "❌ 請輸入正確格式，例如：\n品名\n種類\n廠商\n14000\n1\n11990"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
