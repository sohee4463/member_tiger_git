import os
import json
import pandas as pd
from flask import Flask, request, jsonify
import gspread
from gspread.exceptions import WorksheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from functools import lru_cache
import logging
from flask_cors import CORS

# ✅ 환경 변수 로드 및 기본 설정
load_dotenv()
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)


ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호",
    "제품명", "가격", "PV", "결재방법",
    "주문고객명", "주문자_휴대폰번호", "배송처", "수령확인"
]

@lru_cache()
def get_client():
    keyfile_raw = os.getenv("GOOGLE_SHEET_KEY")
    if not keyfile_raw:
        raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")
    try:
        keyfile_dict = json.loads(keyfile_raw)
        keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
    except Exception as e:
        app.logger.error(f"GOOGLE_SHEET_KEY 파싱 실패: {e}")
        raise ValueError("환경변수 GOOGLE_SHEET_KEY가 JSON 형식이 아닙니다.")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    return gspread.authorize(creds)

def get_members_sheet():
    client = get_client()
    try:
        return client.open(MEMBERS_SPREADSHEET_NAME).worksheet(MEMBERS_SHEET_NAME)
    except Exception as e:
        app.logger.error(f"회원 시트 접근 오류: {e}")
        raise

def get_order_sheet():
    client = get_client()
    try:
        ss = client.open(ORDER_SPREADSHEET_NAME)
        try:
            sheet = ss.worksheet(ORDER_SHEET_NAME)
        except WorksheetNotFound:
            sheet = ss.add_worksheet(title=ORDER_SHEET_NAME, rows="1000", cols="20")
        if "회원명" not in sheet.row_values(1):
            sheet.append_row(ORDER_HEADERS)
        return sheet
    except Exception as e:
        app.logger.error(f"제품 주문 시트 접근 오류: {e}")
        raise

def get_bonus_sheet():
    client = get_client()
    try:
        ss = client.open(BONUS_SPREADSHEET_NAME)
        try:
            return ss.worksheet(BONUS_SHEET_NAME)
        except WorksheetNotFound:
            return ss.add_worksheet(title=BONUS_SHEET_NAME, rows="1000", cols="50")
    except Exception as e:
        app.logger.error(f"후원수당 시트 접근 오류: {e}")
        raise

@app.route("/")
def index():
    return jsonify({"message": "Flask 서버가 정상 작동 중입니다."})

@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        # 🔐 간단한 API Key 인증
        if request.headers.get("x-api-key") != API_KEY:
            return jsonify({"error": "인증 실패: API Key가 유효하지 않습니다."}), 401

        data = request.get_json()
        name = data.get("name", "").strip().lower()

        if not name:
            return jsonify({"error": "이름을 입력해야 합니다."}), 400

        sheet = get_members_sheet()
        values = sheet.get_all_values()
        headers = values[0]
        df = pd.DataFrame(values[1:], columns=headers)

        df["회원명_정규화"] = df["회원명"].astype(str).str.strip().str.lower()
        match = df[df["회원명_정규화"] == name]

        if match.empty:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

        row = match.iloc[0]

        # 🔒 민감 정보 제외한 필드
        exposed_fields = [
            "회원명", "휴대폰번호", "회원번호", "가입일자", "생년월일",
            "통신사", "친밀도", "근무처", "계보도", "소개한분", "주소", "메모",
            "분류", "회원단계", "연령/성별", "직업", "가족관계", "니즈",
            "애용제품", "콘텐츠", "습관챌린지", "비즈니스시스템", "GLC프로젝트", "리더님", "NO"
        ]

        result = {field: row.get(field, "") for field in exposed_fields if field in row}
        return jsonify(result)

    except Exception as e:
        app.logger.exception("회원 검색 오류")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
