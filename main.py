from flask import Flask, request, abort
import os
import json

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
def 推算工錢(售價, 重量_錢, 金價_元_per_錢):
    金料成本 = 重量_錢 * 金價_元_per_錢
    加工費 = 售價 - 金料成本
    return round(加工費, 2)

# 處理文字訊息事件
@handler.add(MessageEvent, message=V3TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    lines = text.splitlines()

    try:
        if not lines[0].startswith("售") or len(lines) < 3:
            raise ValueError("格式錯誤")

        售價 = float(lines[0].replace("售", "").strip())
        重量 = float(lines[1].strip())
        金價 = float(lines[2].strip())

        加工費 = 推算工錢(售價, 重量, 金價)

        reply_text = (
            f"🧾 計算結果：\n\n"
            f"💰 售價：{售價} 元\n"
            f"⚖️ 重量：{重量} 錢\n"
            f"📈 金價：{金價} 元/錢\n\n"
            f"✅ 推算加工費：{加工費:.2f} 元"
        )

    except Exception:
        reply_text = "❌ 請輸入正確格式，如：\n售28000\n3.2\n7700"

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
