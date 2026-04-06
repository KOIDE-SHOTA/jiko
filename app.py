# coding: utf-8
import uuid
import requests
SUPABASE_URL = "https://tqxrfbjzfuqeorgvndve.supabase.co"
SUPABASE_KEY = "sb_publishable_Jayhk0qbNe3klwk55y1oaA_YqL8kSRV"

import os
from PIL import Image, ImageDraw, ImageFont
import io

from flask import Flask, render_template, request, jsonify, session
import anthropic
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, template_folder=".")
app.secret_key = os.environ.get("SECRET_KEY", "jiko-secret")
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

QUESTIONS = [
    "まず、あなたが今まで一番頑張ったことを教えてください",
    "その経験の中で、一番大変だったことは何でしたか",
    "普段、何かを決めるときってどんなふうに考えますか",
    "友達や周りの人からこういう人だよねって言われることはありますか",
    "あなたが一番得意なことや自然とできちゃうことって何ですか",
    "逆に苦手なことやここちょっと弱いなと感じることはありますか",
    "将来どんなふうに働きたいというイメージはありますか",
    "就活や自己分析を通じて一番知りたいことを教えてください"
]

SYSTEM_PROMPT = "You are a friendly Japanese AI assistant helping job-seeking students with self-analysis. Respond in Japanese, warmly and concisely in 3-5 lines."

@app.route("/")
def index():
    session.clear()
    return render_template("index.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/api/start", methods=["POST"])
def start():
    data = request.json
    nickname = data.get("nickname", "あなた")
    mbti = data.get("mbti", "")
    session["nickname"] = nickname
    session["mbti"] = mbti
    session["question_index"] = 0
    session["history"] = []
    session["state"] = "waiting_answer"
    first_q = QUESTIONS[0]
    welcome = "よろしく、" + nickname + "さん！MBTIは" + mbti + "なんだね。8つの質問に答えてね！\n\n" + first_q
    return jsonify({"message": welcome, "question_index": 0})

@app.route("/api/message", methods=["POST"])
def message():
    data = request.json
    user_message = data.get("message", "")
    q_index = session.get("question_index", 0)
    history = session.get("history", [])
    state = session.get("state", "waiting_answer")
    history.append({"role": "user", "content": user_message})
    session["history"] = history
    if state == "waiting_answer":
        session["state"] = "waiting_followup"
        prompt = "ユーザーが「" + QUESTIONS[q_index] + "」に「" + user_message + "」と答えました。深掘り質問を1つだけ短く聞いてください。"
        response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=200, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}])
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        session["history"] = history
        return jsonify({"message": reply, "question_index": q_index, "done": False})
    else:
        session["state"] = "waiting_answer"
        next_index = q_index + 1
        session["question_index"] = next_index
        if next_index >= 8:
            return jsonify({"message": "全部答えてくれてありがとう！診断してみよう", "question_index": 8, "done": True})
        next_q = QUESTIONS[next_index]
        prompt = "一言で受け止めて、次の質問に自然につなげてください。質問：" + next_q
        response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=200, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}])
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        session["history"] = history
        return jsonify({"message": reply, "question_index": next_index, "done": False})
def generate_ogp(adj1, adj2, character, message):
    img = Image.new("RGB", (1200, 630), color="#f0e6f6")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1200, 630], fill="#f0e6f6")
    draw.text((600, 200), adj1 + adj2 + " " + character, fill="#9575cd", anchor="mm")
    draw.text((600, 350), message, fill="#555555", anchor="mm")
    draw.text((600, 500), "jikoキャラ診断", fill="#ce93d8", anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

@app.route("/diagnose")
def diagnose():
    history = session.get("history", [])
    mbti = session.get("mbti", "")
    nickname = session.get("nickname", "あなた")
    conv = "\n".join([m["role"] + ": " + m["content"] for m in history])
    prompt = "以下は就活生との会話です。MBTIは" + mbti + "です。\n\n" + conv + "\n\nこの人のキャラクターを以下の形式でJSONのみで返してください。{\"character\": \"羅針盤\", \"adj1\": \"慎重で\", \"adj2\": \"芯のある\", \"strength\": \"強みの説明\", \"personality\": \"性格特徴の説明\", \"message\": \"一言メッセージ\"}"
    response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=500, system="You are a character diagnosis AI. Return only valid JSON.", messages=[{"role": "user", "content": prompt}])
    import json
    text = response.content[0].text
    try:
        result = json.loads(text)
    except:
        result = {"character": "羅針盤", "adj1": "慎重で", "adj2": "芯のある", "strength": "分析力があります", "personality": "じっくり考えるタイプです", "message": "あなたらしく進もう"}
    session["result"] = result
    slug = str(uuid.uuid4())[:8]
    requests.post(SUPABASE_URL + "/rest/v1/result", headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"}, json={"slug": slug, "nickname": nickname, "mbti": mbti, "character": result.get("character",""), "adj1": result.get("adj1",""), "adj2": result.get("adj2",""), "strength": result.get("strength",""), "personality": result.get("personality",""), "message": result.get("message","")})
    session["slug"] = slug
    ogp_buf = generate_ogp(result.get("adj1",""), result.get("adj2",""), result.get("character",""), result.get("message",""))
    session["ogp"] = ogp_buf.getvalue().hex()

    return render_template("result.html", result=result, nickname=nickname, slug=session.get("slug",""))
 
@app.route("/ogp/<slug>.png")
def ogp_image(slug):
    from flask import send_file
    ogp_hex = session.get("ogp", "")
    if not ogp_hex:
        return "", 404
    buf = io.BytesIO(bytes.fromhex(ogp_hex))
    return send_file(buf, mimetype="image/png")
@app.route("/result/<slug>")
def result_page(slug):
    import requests as req
    res = req.get(SUPABASE_URL + "/rest/v1/result?slug=eq." + slug, headers={"apikey": SUPABASE_KEY})
    data = res.json()
    if not data:
        return "結果が見つかりません", 404
    row = data[0]
    result = {"character": row["character"], "adj1": row["adj1"], "adj2": row["adj2"], "strength": row["strength"], "personality": row["personality"], "message": row["message"]}
    return render_template("result.html", result=result, nickname=row["nickname"], slug=slug)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
