import os
import json
from flask import Flask, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# ✅ .env 로딩 및 키 JSON 읽기
load_dotenv()
keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))

# ✅ private_key 줄바꿈 복원
keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")

# ✅ Google Sheets 인증
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("members_list_main").worksheet("DB")

# ✅ Flask 앱 생성
app = Flask(__name__)

# ✅ 홈 라우팅
@app.route("/")
def home():
    return render_template("index.html")

# ✅ 이름으로만 정확히 찾기
@app.route("/find_member", methods=["POST"])
def find_member():
    data = request.get_json()
    name_to_find = data.get("name", "").strip()
    if not name_to_find:
        return jsonify({"error": "이름이 필요합니다."}), 400

    all_data = sheet.get_all_records()
    result = [row for row in all_data if row.get("회원명") == name_to_find]
    return jsonify(result)

# ✅ 이름 or 전화번호 부분 일치로 필터
@app.route("/search", methods=["POST"])
def search_member():
    data = request.get_json()
    name = data.get("name", "").strip().lower()
    phone = data.get("phone", "").strip()

    records = sheet.get_all_records()
    results = [
        row for row in records
        if (name and name in row["회원명"].lower()) or
           (phone and phone in row["휴대폰번호"])
    ]
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
