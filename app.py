from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerMessage, ImageMessage, VideoMessage, LocationMessage
import os
import google.generativeai as genai

app = Flask(__name__)

# LINE 和 Gemini 憑證等
LINE_CHANNEL_ACCESS_TOKEN = 'LK0YWhVkd7q1U3DQvMLb4SLc6dgAU5BDLfUbgyOc8Avx8JhewsTL1odWitsuqumvKfzMBsdoHvDD04dNTFlHhGhY7IRExTQFLMqHF9m895Kk9UrdGoYcAzsuLMfezGERdXhltoQnDC6pTne2jfVwWwdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'abe1a07af1641536aa395021aac205e5'
GEMINI_API_KEY = 'AIzaSyCT24jBCc1FMDl6jTcCSxwoeZYVlRBim68'

# Init LINE Bot
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Init Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-pro')

# 儲存對話紀錄用
conversation_history = []

# Webhook , 接收 LINE 訊息
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_message = event.message.text
    conversation_history.append({"user": user_message})
    
    try:
        # 檢查訊息是否包含 "你好"
        if "你好" in user_message:
            reply_text = "你好哇！"
        else:
            response = model.generate_content(user_message)
            reply_text = response.text
    except Exception as e:
        print(f"Gemini API 錯誤: {str(e)}")  # 輸出錯誤訊息到終端機
        reply_text = "抱歉，我出錯了>∩<！"
    
    conversation_history.append({"bot": reply_text})
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# 處理貼圖
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="哇！是貼圖！")
    )

# 處理圖片
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到你的圖片囉！")
    )

# 處理影片
@handler.add(MessageEvent, message=VideoMessage)
def handle_video_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到你的影片囉！")
    )

# 處理位置
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    location = event.message.address or "某處"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"你在 {location}？")
    )

# GET API：查詢對話紀錄
@app.route("/history", methods=['GET'])
def get_history():
    return {"history": conversation_history}

# DELETE API：刪除對話紀錄
@app.route("/history", methods=['DELETE'])
def delete_history():
    global conversation_history
    conversation_history = []
    return {"message": "對話紀錄已刪除"}

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)