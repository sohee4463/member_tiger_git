import os
import json
from flask import Flask, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# ✅ Flask 앱 생성
app = Flask(__name__)






# ✅ .env 로딩 및 키 JSON 읽기
load_dotenv()
keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))

# ✅ 환경변수 읽기
print("✅ ENV:", os.getenv("GOOGLE_SHEET_KEY"))

# ✅ JSON으로 변환
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



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)



@app.route("/")
def home():
    return render_template("index.html")

import os
from dotenv import load_dotenv
load_dotenv()

print("✅ ENV:", os.getenv("GOOGLE_SHEET_KEY"))  # 값이 None이면 실패


# ✅ 홈 라우팅
@app.route("/")
def home():
    return render_template("index.html")



@app.route('/sheet', methods=['POST'])
def access_sheet():
    data = request.json
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)

    sheet = client.open(data['spreadsheet_name']).worksheet(data['worksheet_name'])
    values = sheet.get_all_values()
    return jsonify(values)



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

