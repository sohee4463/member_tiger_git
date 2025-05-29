import os
import json
from flask import Flask, request, jsonify, render_template
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# ✅ .env 불러오기
load_dotenv()

# ✅ Flask 앱 생성
app = Flask(__name__)

# ✅ Google Sheets 인증 처리
def get_sheet():
    keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("members_list_main").worksheet("DB")
    return sheet

# ✅ 홈 라우팅
@app.route("/")
def home():
    return render_template("index.html")

# ✅ 정확 일치 검색
@app.route("/find_member", methods=["POST"])
def find_member():
    data = request.get_json()
    name_to_find = data.get("name", "").strip()
    if not name_to_find:
        return jsonify({"error": "이름이 필요합니다."}), 400

    sheet = get_sheet()
    all_data = sheet.get_all_records()
    result = [row for row in all_data if row.get("회원명") == name_to_find]
    return jsonify(result)

# ✅ 부분 일치 검색 (이름 or 휴대폰)
@app.route("/search", methods=["POST"])
def search_member():
    data = request.get_json()
    name = data.get("name", "").strip().lower()
    phone = data.get("phone", "").strip()

    sheet = get_sheet()
    records = sheet.get_all_records()
    results = [
        row for row in records
        if (name and name in row["회원명"].lower()) or
           (phone and phone in row["휴대폰번호"])
    ]
    return jsonify(results)

# ✅ 특정 시트 접근 (선택된 시트명/워크시트명으로)
@app.route('/sheet', methods=['POST'])
def access_sheet():
    data = request.get_json()
    sheet_name = data.get("spreadsheet_name")
    worksheet_name = data.get("worksheet_name")

    if not sheet_name or not worksheet_name:
        return jsonify({"error": "시트 이름과 워크시트 이름이 필요합니다."}), 400

    keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open(sheet_name).worksheet(worksheet_name)
    values = sheet.get_all_values()
    return jsonify(values)

# ✅ Render 호환 실행
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
