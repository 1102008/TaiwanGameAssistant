from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    StickerMessage, ImageMessage, ImageSendMessage, VideoMessage, LocationMessage,
    PostbackEvent, TemplateSendMessage, ButtonsTemplate, CarouselTemplate,
    CarouselColumn, URIAction, PostbackAction
)
import json
import random
import os

app = Flask(__name__)

# LINE 憑證
LINE_CHANNEL_ACCESS_TOKEN = 'N0gdfsfL+yTwNO3Cv3d7B3ohXdVU67E29FkunNRvV+XDrjQlJvPYGLd8hSQtFWmKj2D32zuNEkEz4ptgGgsP8f7SA3Zp0FPTf5ZpDt9AeoY9ubLugSyw4IzYMDOXK1nmbSB2WfSRfWvmU7GPhB8+RwdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '234f88f756dbfa506d3a74c9e28e13de'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 儲存資料
conversation_history = []
user_search_state = {}
user_favorites = {}  # 每個 user_id 對應一個最愛清單

# 載入遊戲資料
with open('all_games.json', encoding='utf-8') as f:
    games = json.load(f)

# 讀取最愛清單
FAVORITES_FILE = 'user_favorites.json'
if os.path.exists(FAVORITES_FILE):
    with open(FAVORITES_FILE, encoding='utf-8') as f:
        user_favorites = json.load(f)
else:
    user_favorites = {}

def parse_price(price_str):
    try:
        if "免費" in price_str:
            return 0
        numbers = ''.join(c for c in price_str if c.isdigit())
        return int(numbers)
    except:
        return 999999

def check_game_updates():
    last_file = 'all_games_last.json'
    current_file = 'all_games.json'

    if not os.path.exists(last_file):
        with open(current_file, 'r', encoding='utf-8') as f:
            data = f.read()
        with open(last_file, 'w', encoding='utf-8') as f:
            f.write(data)
        return

    with open(last_file, 'r', encoding='utf-8') as f:
        last_data = json.load(f)
    with open(current_file, 'r', encoding='utf-8') as f:
        current_data = json.load(f)

    last_games = {game['game_name']: game for game in last_data}
    current_games = {game['game_name']: game for game in current_data}

    # 新遊戲偵測
    new_games = [game for name, game in current_games.items() if name not in last_games]
    for user_id in user_favorites:
        if new_games:
            # 先送出一則提示文字
            line_bot_api.push_message(user_id, TextSendMessage(
                text="有新遊戲呢！要不要來看看呀？>U<"
            ))
        for game in new_games:
            s_template = ButtonsTemplate(
                thumbnail_image_url=game['game_image'],
                title=game['game_name'][:40],
                text=f"價格：{game['original_price']}",
                actions=[
                    URIAction(label='遊戲連結', uri=game['link']),
                    PostbackAction(label='加入我的最愛', data=f"action=add_favorite&game_name={game['game_name']}")
                ]
            )
            line_bot_api.push_message(user_id, TemplateSendMessage(
                alt_text="有新遊戲耶～", template=s_template
            ))

    
    # 降價通知
    for user_id, favorites in user_favorites.items():
        sent_notice = False
        for fav_name in favorites:
            if fav_name in last_games and fav_name in current_games:
                old_price = parse_price(last_games[fav_name]['original_price'])
                new_price = parse_price(current_games[fav_name]['original_price'])
                if new_price < old_price:
                    game = current_games[fav_name]  # ✅ 加上這行
                    line_bot_api.push_message(user_id, TextSendMessage(
                        text=f"🎉《{fav_name}》降價啦！\n💰 原價：NT$ {old_price}\n🔥 現在只要：NT$ {new_price}！"
                    ))
                    s_template = ButtonsTemplate(
                        thumbnail_image_url=game['game_image'],
                        title=game['game_name'][:40],
                        text=f"現在價格：{game['original_price']}",
                        actions=[
                            URIAction(label='遊戲連結', uri=game['link']),
                            PostbackAction(label='加入我的最愛', data=f"action=add_favorite&game_name={game['game_name']}")
                        ]
                    )
                    line_bot_api.push_message(user_id, TemplateSendMessage(
                        alt_text=f"《{fav_name}》降價通知", template=s_template
                    ))

    # 寫入新的 last
    with open(last_file, 'w', encoding='utf-8') as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    conversation_history.append({"user": user_message})

    if user_id not in user_search_state:
        user_search_state[user_id] = {"step": None, "data": {}}
    state = user_search_state[user_id]

    # --- 主指令 ---
    if user_message == "你好":
        reply_text = "你好哇！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    elif "介紹" in user_message:
        reply_text = "我是台灣遊戲小幫手～下方選單有4個功能任君挑選！希望你能喜歡的台灣遊戲喔！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    elif user_message == "搜尋遊戲":
        state["step"] = "ask_by_name"
        state["data"] = {}
        buttons_template = ButtonsTemplate(
            title="搜尋遊戲",
            text="你想用遊戲名稱搜尋嗎？",
            actions=[
                PostbackAction(label="是", data="search_step=wait_game_name"),
                PostbackAction(label="否", data="search_step=ask_by_dev")
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text="是否用遊戲名稱搜尋？", template=buttons_template)
        )
        return

    # --- 搜尋流程 ---
    if state["step"] == "wait_game_name":
        state["data"]["game_name"] = user_message
        state["step"] = None  # 等待按鈕回覆，不再等文字輸入

        buttons_template = ButtonsTemplate(
            title="開發者搜尋",
            text="你想用開發者名稱搜尋嗎？",
            actions=[
                PostbackAction(label="是", data="search_step=wait_dev_name"),
                PostbackAction(label="否", data="search_step=ask_by_tag")
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text="是否使用開發者名稱搜尋？", template=buttons_template)
        )
        return

    if state["step"] == "ask_by_dev":
        if user_message == "是":
            state["step"] = "wait_dev_name"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入開發者名稱："))
        else:
            state["step"] = "ask_by_tag"
            buttons_template = ButtonsTemplate(
                title="標籤過濾",
                text="你想使用標籤過濾嗎？",
                actions=[
                    PostbackAction(label="是", data="search_step=wait_tag"),
                    PostbackAction(label="否", data="search_step=filter_games")
                ]
            )
            line_bot_api.reply_message(
                event.reply_token,
                TemplateSendMessage(alt_text="是否使用標籤過濾？", template=buttons_template)
            )
        return

    if state["step"] == "wait_dev_name":
        state["data"]["developer"] = user_message
        state["step"] = None  # 等待 Postback 回覆，不處理文字
        buttons_template = ButtonsTemplate(
            title="標籤過濾",
            text="你想使用標籤過濾嗎？",
            actions=[
                PostbackAction(label="是", data="search_step=wait_tag"),
                PostbackAction(label="否", data="search_step=filter_games")
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,  
            TemplateSendMessage(alt_text="是否使用標籤過濾？", template=buttons_template)
        )
        return

    if state["step"] == "ask_by_tag":
        buttons_template = ButtonsTemplate(
            title="標籤過濾",
            text="你想使用標籤過濾嗎？",
            actions=[
                PostbackAction(label="是", data="search_step=wait_tag"),
                PostbackAction(label="否", data="search_step=filter_games")
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text="是否使用標籤過濾？", template=buttons_template)
        )
        state["step"] = None  # 避免同時又走到文字判斷，等待用戶按鈕回覆
        return

    if state["step"] == "wait_tag":
        state["data"]["tag"] = user_message
        state["step"] = "filter_games"
        return filter_and_reply_games(event, user_id)

    if state["step"] == "wait_exact_game_name":
        selected_name = user_message.strip().lower()
        candidates = state["data"].get("candidates", [])
        matched = [g for g in candidates if selected_name == g["game_name"].lower()]

        if not matched:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="找不到這款遊戲，請確認名稱是否正確。"))
        elif len(matched) == 1:
            game = matched[0]
            buttons_template = ButtonsTemplate(
                thumbnail_image_url=game['game_image'],
                title=game['game_name'][:40],
                text=f"價格：{game['original_price']}",
                actions=[
                    URIAction(label='遊戲連結', uri=game['link']),
                    PostbackAction(label='加入我的最愛', data=f"action=add_favorite&game_name={game['game_name']}")
                ]
            )
            template_message = TemplateSendMessage(
                alt_text='推薦遊戲',
                template=buttons_template
            )
            line_bot_api.reply_message(event.reply_token, template_message)
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="找到多筆相符遊戲，請再試一次輸入完整名稱。"))

        user_search_state[user_id] = {"step": None, "data": {}}
        return
        
    elif user_message == "我的最愛":
        favorites = user_favorites.get(user_id, [])

        if not favorites:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="你目前還沒有加入任何最愛遊戲喔！"))
            return

        # 找出符合 favorites 名稱的遊戲資料
        favorite_games = [g for g in games if g["game_name"] in favorites]

        # CarouselTemplate 最多 10 個 columns
        columns = []
        for g in favorite_games[:10]:
            column = CarouselColumn(
                thumbnail_image_url=g['game_image'],
                title=g['game_name'][:40],
                text=f"價格：{g['original_price']}",
                actions=[
                    URIAction(label="遊戲連結", uri=g["link"]),
                    PostbackAction(label="從最愛移除", data=f"action=remove_favorite&game_name={g['game_name']}")
                ]
            )
            columns.append(column)

        carousel_template = CarouselTemplate(columns=columns)
        template_message = TemplateSendMessage(
            alt_text="你的最愛遊戲列表", template=carousel_template
        )

        line_bot_api.reply_message(event.reply_token, template_message)
        return

    elif user_message == "隨機推薦":
        game = random.choice(games)
        buttons_template = ButtonsTemplate(
            thumbnail_image_url=game['game_image'],
            title=game['game_name'][:40],
            text=f"價格：{game['original_price']}",
            actions=[
                URIAction(label='遊戲連結', uri=game['link']),
                PostbackAction(label='加入我的最愛', data=f"action=add_favorite&game_name={game['game_name']}")
            ]
        )
        template_message = TemplateSendMessage(
            alt_text='推薦遊戲',
            template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        return

    # fallback
    reply_text = f"你剛剛說的是：「{user_message}」嗎？我還沒學會回答你的問題呢 >_<"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

def filter_and_reply_games(event, user_id):
    state = user_search_state[user_id]
    filters = state["data"]

    filtered = games
    if "game_name" in filters:
        filtered = [g for g in filtered if filters["game_name"].lower() in g["game_name"].lower()]
    if "developer" in filters:
        filtered = [g for g in filtered if filters["developer"].lower() in g.get("developer", "").lower()]
    if "tag" in filters:
        filtered = [g for g in filtered if filters["tag"] in g.get("tags", [])]

    if not filtered:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="找不到符合條件的遊戲 😢"))
        user_search_state[user_id] = {"step": None, "data": {}}
        return

    if len(filtered) == 1:
        game = filtered[0]
        buttons_template = ButtonsTemplate(
            thumbnail_image_url=game['game_image'],
            title=game['game_name'][:40],
            text=f"價格：{game['original_price']}",
            actions=[
                URIAction(label='遊戲連結', uri=game['link']),
                PostbackAction(label='加入我的最愛', data=f"action=add_favorite&game_name={game['game_name']}")
            ]
        )
        template_message = TemplateSendMessage(
            alt_text='推薦遊戲',
            template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        user_search_state[user_id] = {"step": None, "data": {}}
        return

    # 若多筆，請使用者輸入完整名稱
    summary_lines = [f"🎮 {g['game_name']}" for g in filtered]
    count_text = f"共 {len(filtered)} 筆符合條件的遊戲"
    summary_text = f"🔍 搜尋結果如下：\n{count_text}\n\n" + "\n".join(summary_lines)
    if len(summary_text) > 4000:
        summary_text = summary_text[:4000] + "\n（內容過長，部分結果省略）"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text=summary_text + "\n\n請輸入你想看的完整遊戲名稱："))

    # 設定下一步等使用者輸入精確名稱
    state["step"] = "wait_exact_game_name"
    state["data"]["candidates"] = filtered  # 暫存候選遊戲清單
    
def save_favorites():
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_favorites, f, ensure_ascii=False, indent=2)

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    params = dict(param.split('=') for param in data.split('&'))
    user_id = event.source.user_id

    if user_id not in user_search_state:
        user_search_state[user_id] = {"step": None, "data": {}}
    state = user_search_state[user_id]

    # ✅ 加入最愛
    if params.get('action') == 'add_favorite':
        game_name = params.get('game_name', '未知遊戲')

        if user_id not in user_favorites:
            user_favorites[user_id] = []

        if game_name not in user_favorites[user_id]:
            user_favorites[user_id].append(game_name)
            save_favorites()
            reply_text = f"✅ 已將「{game_name}」加入你的最愛！"

        else:
            reply_text = f"⚠️ 「{game_name}」已在你的最愛清單中喔～"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return
    elif params.get('action') == 'remove_favorite':
        game_name = params.get('game_name', '')
        if game_name in user_favorites.get(user_id, []):
            user_favorites[user_id].remove(game_name)
            save_favorites()
            reply_text = f"✅ 已將「{game_name}」從最愛移除！"
        else:
            reply_text = f"⚠️「{game_name}」不在你的最愛清單中喔！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # ✅ 搜尋遊戲流程
    if params.get("search_step") == "wait_game_name":
        state["step"] = "wait_game_name"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入遊戲名稱："))

    elif params.get("search_step") == "ask_by_dev":
        state["step"] = "ask_by_dev"
        buttons_template = ButtonsTemplate(
            title="開發者搜尋",
            text="你想用開發者名稱搜尋嗎？",
            actions=[
                PostbackAction(label="是", data="search_step=wait_dev_name"),
                PostbackAction(label="否", data="search_step=ask_by_tag")
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text="是否使用開發者搜尋？", template=buttons_template)
        )

    elif params.get("search_step") == "wait_dev_name":
        state["step"] = "wait_dev_name"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入開發者名稱："))

    elif params.get("search_step") == "ask_by_tag":
        state["step"] = "ask_by_tag"
        buttons_template = ButtonsTemplate(
            title="標籤過濾",
            text="你想使用標籤過濾嗎？",
            actions=[
                PostbackAction(label="是", data="search_step=wait_tag"),
                PostbackAction(label="否", data="search_step=filter_games")
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text="是否使用標籤過濾？", template=buttons_template)
        )

    elif params.get("search_step") == "wait_tag":
        state["step"] = "wait_tag"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入標籤："))

    elif params.get("search_step") == "filter_games":
        state["step"] = "filter_games"
        filter_and_reply_games(event, user_id)
        
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="哇！你傳了貼圖給我！\n不過很可惜我還沒有學會解析貼圖>∩<"))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="哇！你傳了圖片給我！\n不過很可惜我還沒有學會解析圖片>∩<"))

@handler.add(MessageEvent, message=VideoMessage)
def handle_video_message(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="哇！你傳了影片給我！\n不過很可惜我還沒有學會解析影片>∩<"))

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    location = event.message.address or "某處"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="哇！你傳了一個地址給我！\n不過很可惜我還沒有學會解析地址>∩<"))

@app.route("/history", methods=['GET'])
def get_history():
    return {"history": conversation_history}

@app.route("/history", methods=['DELETE'])
def delete_history():
    global conversation_history
    conversation_history = []
    return {"message": "對話紀錄已刪除"}

if __name__ == "__main__":
    check_game_updates()  # 啟動時檢查有沒有新遊戲或降價
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)