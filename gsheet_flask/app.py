import os
import json
import gspread
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 🔐 환경변수에서 JSON 키 읽기
keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))

keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")  # 역변환 추가



scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
client = gspread.authorize(creds)

# 🔎 워크시트 열기
sheet = client.open("members_list_main").worksheet("DB")

@app.route("/")
def home():
    return "✅ Flask 서버 실행 중!"

@app.route("/find_member", methods=["POST"])
def find_member():
    data = request.get_json()
    name_to_find = data.get("name", "").strip()
    if not name_to_find:
        return jsonify({"error": "이름이 필요합니다."}), 400

    all_data = sheet.get_all_records()
    result = [row for row in all_data if row.get("회원명") == name_to_find]
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
