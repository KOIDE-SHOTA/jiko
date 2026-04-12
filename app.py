# coding: utf-8
import uuid
import json
import io
import os

import requests
from PIL import Image, ImageDraw
from flask import Flask, render_template, request, jsonify, session, send_file
import anthropic
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = "https://tqxrfbjzfuqeorgvndve.supabase.co"
SUPABASE_KEY = "sb_publishable_Jayhk0qbNe3klwk55y1oaA_YqL8kSRV"

app = Flask(__name__, template_folder=".", static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "jiko-secret-2024")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

QUESTIONS = [
    "就職先の希望や、譲れない条件はある？",
    "どんなことでもいいから、気づいたらできてた・続いてたことって何かある？",
    "アルバイトや学校のことで悩みごとがあるとき、いつもどうしてる？",
    "仲良くしてる人はどれくらいいる？どんな人が多い？",
]

TOTAL_QUESTIONS = 4

def should_followup_with_rescue(q_index, user_answer):
    if q_index not in [1, 3]:
        return False
    question_map = {
        1: "気づいたらできてた・続いてたことは何かある？",
        3: "仲良くしてる人はどれくらいいる？どんな人が多い？"
    }
    question = question_map[q_index]
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=10,
        system="質問に対して何かしら答えようとしているか判定してください。答えようとしていればyes、答えられない・わからないと言っていればnoを返してください。yesかnoだけ返してください。",
        messages=[{"role": "user", "content": f"質問：{question}\n回答：{user_answer}"}]
    )
    result = response.content[0].text.strip().lower()
    return result == "no"

def get_followup_prompt(q_index, user_answer):
    is_rescue = should_followup_with_rescue(q_index, user_answer)
    if q_index == 0:
        return (
            f"就活生が「就職先の希望や譲れない条件」について「{user_answer}」と答えました。"
            "長期的に死守したいもの・今欲しているものについて、どちらかまたは両方をフレンドリーに深掘りしてください。"
            "1〜2文で自然に聞いてください。"
        )
    elif q_index == 1:
        if is_rescue:
            return (
                "就活生が「気づいたらできてた・続いてたこと」について答えられませんでした。"
                "共感表現（難しいよね・わかるよ等）は使わず、同じテーマを別の角度からすぐ聞き直してください。1文で。"
            )
        else:
            return (
                f"就活生が「{user_answer}」と答えました。"
                "「そのために大切だったと思うことは？」と自然に深掘りしてください。1〜2文で。"
            )
    elif q_index == 2:
        return (
            f"就活生が悩みへの対処について「{user_answer}」と答えました。"
            "「一人で抱え込むことが多い感じ？」など近そうな思考パターンを自然に確認してください。1〜2文で。"
        )
    elif q_index == 3:
        if is_rescue:
            return (
                "就活生が仲良くしてる人について答えられませんでした。"
                "共感表現は使わず、どんな人と過ごしたいかを別の角度からすぐ聞き直してください。1文で。"
            )
        else:
            return (
                f"就活生が「{user_answer}」と答えました。"
                "「その人たちとどんな話や過ごし方をすることが多い？」と深掘りしてください。1〜2文で。"
            )
    return f"「{user_answer}」という回答について、もう少し詳しく聞かせてもらえますか？"
ADJECTIVE_LIST = """
【対人・調和系】温かい、真っ直ぐな、聞き上手な、頼もしい、人懐っこい、謙虚な、お節介な、朗らかな、包容力のある、誠実な、気配り上手な、穏やかな、情熱的な、愛嬌のある、裏表のない、献身的な、凛とした、柔らかい、親身な、礼儀正しい
【思考・分析系】鋭い、冷静な、思慮深い、合理的な、独創的な、ストイックな、ロジカルな、慎重な、好奇心旺盛な、マニアックな、粘り強い、先見の明がある、抜け目のない、現実的な、柔軟な、緻密な、本質を突く、知的な、疑り深い、多才な
【行動・エナジー系】軽快な、パワフルな、不屈の、マイペースな、型破りな、大胆な、フットワークの軽い、アクティブな、ストレートな、チャーミングな、エネルギッシュな、淡々とした、遊び心のある、泥臭い、スマートな、ひたむきな、スピーディーな、タフな、自由奔放な、意志の強い
"""

CHARACTER_LIST = """
コンパス（地図描き）、懐中電灯（探索者）、万年筆（貴族魔術師）、金槌（ドワーフ戦士）、セロハンテープ（工作士）、砥石（侍）、潤滑油（整備士）、定規（重騎士）、拡声器（詩人）、キャンバス（絵師）、パラシュート（曲芸師）、エンジン（魔導ゴーレム）、フィルター（錬金術師）、アンテナ（斥候）、辞書（老魔術師）、ピンセット（細工師）、スパイス（料理師）、望遠鏡（占星術師）、充電器（雷の魔術師）、バトン（走者）
"""

CHARACTER_IMAGE_MAP = {
    "コンパス": "compass.png",
    "懐中電灯": "flashlight.png",
    "万年筆": "fountain_pen.png",
    "金槌": "hammer.png",
    "セロハンテープ": "tape.png",
    "砥石": "whetstone.png",
    "潤滑油": "lubricant.png",
    "定規": "ruler.png",
    "拡声器": "megaphone.png",
    "キャンバス": "canvas.png",
    "パラシュート": "parachute.png",
    "エンジン": "engine.png",
    "フィルター": "filter.png",
    "アンテナ": "antenna.png",
    "辞書": "dictionary.png",
    "ピンセット": "tweezers.png",
    "スパイス": "spice.png",
    "望遠鏡": "telescope.png",
    "充電器": "charger.png",
    "バトン": "baton.png",
}

SYSTEM_PROMPT_CHAT = (
    "あなたは就活生の自己分析を手伝うフレンドリーなAIアシスタントです。"
    "日本語で、温かく・簡潔に（1〜2文）で深掘り質問だけしてください。"
    "フィードバックや評価はしないでください。"
)

SYSTEM_PROMPT_EXTRACT = (
    "あなたは就活生の回答を分析するAIです。"
    "会話内容から以下の4項目を単語・短フレーズで抽出してください。"
    "回答をそのまま引用しないでください。"
    "必ず以下のJSON形式のみで返してください（前後に説明文・コードブロック不要）。"
)

SYSTEM_PROMPT_DIAGNOSE = (
    "あなたはキャラクター診断AIです。"
    "渡された特徴データだけを材料に診断結果を生成してください。"
    "元の会話・回答は参照しないでください。"
    "各項目で同じ表現を繰り返さないでください。回答の引用も禁止です。"
    "必ず以下のJSON形式のみで返してください（前後に説明文・コードブロック不要）。"
)


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
    welcome = (
        f"よろしく、{nickname}さん！MBTIは{mbti}なんだね。\n\n"
        f"4つの質問に答えてもらうよ。気軽に話してくれると嬉しい😊\n\n"
        f"Q1. {first_q}"
    )
    return jsonify({"message": welcome, "question_index": 0, "total": TOTAL_QUESTIONS, "done": False})


@app.route("/api/message", methods=["POST"])
def message():
    data = request.json
    user_message = data.get("message", "")
    q_index = session.get("question_index", 0)
    history = session.get("history", [])
    state = session.get("state", "waiting_answer")
    history.append({"role": "user", "content": user_message})
    if state == "waiting_answer":
        session["state"] = "waiting_followup"
        followup_prompt = get_followup_prompt(q_index, user_message)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system=SYSTEM_PROMPT_CHAT,
            messages=[{"role": "user", "content": followup_prompt}]
        )
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        session["history"] = history
        return jsonify({"message": reply, "question_index": q_index, "total": TOTAL_QUESTIONS, "done": False})
    else:
        session["state"] = "waiting_answer"
        next_index = q_index + 1
        session["question_index"] = next_index
        if next_index >= TOTAL_QUESTIONS:
            history.append({"role": "assistant", "content": "ありがとう！"})
            session["history"] = history
            return jsonify({
                "message": "ありがとう、全部教えてくれて！準備ができたら「診断する」ボタンを押してね✨",
                "question_index": TOTAL_QUESTIONS,
                "total": TOTAL_QUESTIONS,
                "done": True
            })
        next_q = QUESTIONS[next_index]
        reply = f"Q{next_index + 1}. {next_q}"
        history.append({"role": "assistant", "content": reply})
        session["history"] = history
        return jsonify({
            "message": reply,
            "question_index": next_index,
            "total": TOTAL_QUESTIONS,
            "done": False
        })
@app.route("/diagnose")
def diagnose():
    history = session.get("history", [])
    mbti = session.get("mbti", "")
    nickname = session.get("nickname", "あなた")
    session_id = str(uuid.uuid4())
    conv = "\n".join([f"{m['role']}: {m['content']}" for m in history])

    extract_prompt = f"""以下は就活生（MBTI: {mbti}）との会話です。

{conv}

以下の4項目を単語・短フレーズで抽出してください。回答をそのまま引用しないでください。

{{
  "行動傾向": "例）締め切り直前に動く",
  "判断基準": "例）感情優先",
  "対人距離": "例）深く狭く",
  "ストレス癖": "例）一人で抱える"
}}"""

    extract_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT_EXTRACT,
        messages=[{"role": "user", "content": extract_prompt}]
    )
    extract_text = extract_response.content[0].text.strip()
    if extract_text.startswith("```"):
        extract_text = extract_text.split("```")[1]
        if extract_text.startswith("json"):
            extract_text = extract_text[4:]
    extract_text = extract_text.strip().rstrip("```").strip()
    try:
        traits = json.loads(extract_text)
    except Exception:
        traits = {"行動傾向": "不明", "判断基準": "不明", "対人距離": "不明", "ストレス癖": "不明"}

    diagnose_prompt = f"""以下の特徴データを持つ就活生（MBTI: {mbti}）の診断結果を生成してください。

【特徴データ】
{json.dumps(traits, ensure_ascii=False, indent=2)}

以下の形容詞リストから2つ、道具リストから1つ必ず選んでください。リスト外の言葉は使わないでください。

【形容詞リスト】
{ADJECTIVE_LIST}

【道具リスト】
{CHARACTER_LIST}

診断結果を以下のJSON形式のみで返してください：
{{
  "adj1": "〇〇な",
  "adj2": "△△な",
  "character": "道具名のみ（例：コンパス）",
  "character_desc": "キャラクターの説明（2〜3文）",
  "strength": "強み（行動特性ベース・2〜3文）",
  "blind_spot": "盲点・弱み（2〜3文）",
  "long_term": "長期動機：何を死守したいか（1〜2文）",
  "short_term": "短期動機：今何が欲しいか（1〜2文）",
  "message": "だからこう動けるという示唆（1〜2文・前向きに締める）"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=SYSTEM_PROMPT_DIAGNOSE,
        messages=[{"role": "user", "content": diagnose_prompt}]
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("```").strip()
    try:
        result = json.loads(text)
    except Exception:
        result = {
            "adj1": "慎重な",
            "adj2": "誠実な",
            "character": "コンパス",
            "character_desc": "方向を示す、迷わない人。",
            "strength": "物事を丁寧に考えて行動できます。",
            "blind_spot": "慎重すぎて動き出しが遅くなることがあります。",
            "long_term": "自分らしく働ける環境を大切にしたい。",
            "short_term": "まず一歩、動き出すきっかけが欲しい。",
            "message": "あなたの丁寧さが、きっと誰かの道しるべになる。"
        }

    char_name = result.get("character", "コンパス")
    result["image"] = CHARACTER_IMAGE_MAP.get(char_name, "compass.png")
    session["result"] = result
    slug = str(uuid.uuid4())[:8]

    try:
        requests.post(
            SUPABASE_URL + "/rest/v1/result",
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={
                "slug": slug,
                "nickname": nickname,
                "mbti": mbti,
                "character": result.get("character", ""),
                "adj1": result.get("adj1", ""),
                "adj2": result.get("adj2", ""),
                "character_desc": result.get("character_desc", ""),
                "strength": result.get("strength", ""),
                "blind_spot": result.get("blind_spot", ""),
                "long_term": result.get("long_term", ""),
                "short_term": result.get("short_term", ""),
                "message": result.get("message", ""),
            },
            timeout=5
        )
    except Exception:
        pass

    try:
        answers = [m["content"] for m in history if m["role"] == "user"]
        while len(answers) < 8:
            answers.append("")
        requests.post(
            SUPABASE_URL + "/rest/v1/chat_logs",
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={
                "session_id": session_id,
                "q1": answers[0], "q2": answers[2], "q3": answers[4], "q4": answers[6],
                "followup1": answers[1], "followup2": answers[3], "followup3": answers[5], "followup4": answers[7],
                "final_character": result.get("character", ""),
            },
            timeout=5
        )
    except Exception:
        pass

    session["slug"] = slug
    return render_template("result.html", result=result, nickname=nickname, slug=slug)


@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.json
    slug = data.get("slug", "")
    score = data.get("score", 0)
    matched_items = data.get("matched_items", [])
    try:
        requests.post(
            SUPABASE_URL + "/rest/v1/feedback",
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={"slug": slug, "score": score, "matched_items": matched_items},
            timeout=5
        )
    except Exception:
        pass
    return jsonify({"status": "ok"})


@app.route("/ogp/<slug>.png")
def ogp_image(slug):
    try:
        res = requests.get(
            SUPABASE_URL + f"/rest/v1/result?slug=eq.{slug}",
            headers={"apikey": SUPABASE_KEY},
            timeout=5
        )
        data = res.json()
        if data:
            img = Image.new("RGB", (1200, 630), color=(10, 15, 40))
            draw = ImageDraw.Draw(img)
            draw.rectangle([20, 20, 1180, 610], outline=(212, 175, 55), width=2)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return send_file(buf, mimetype="image/png")
    except Exception:
        pass
    return "", 404


@app.route("/result/<slug>")
def result_page(slug):
    try:
        res = requests.get(
            SUPABASE_URL + f"/rest/v1/result?slug=eq.{slug}",
            headers={"apikey": SUPABASE_KEY},
            timeout=5
        )
        data = res.json()
        if data:
            row = data[0]
            return render_template("result.html", result=row, nickname=row.get("nickname", ""), slug=slug)
    except Exception:
        pass
    return "結果が見つかりませんでした", 404


@app.route("/googlec77b838e118c8e2c.html")
def google_verify():
    return render_template("googlec77b838e118c8e2c.html")


if __name__ == "__main__":
    app.run(debug=True)
