import os
import json
import pandas as pd
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime
from functools import lru_cache
import logging
import mimetypes
from flask_cors import CORS






load_dotenv()
app = Flask(__name__)



CORS(app)
logging.basicConfig(level=logging.INFO)

SHEET_NAME = os.getenv("SHEET_NAME", "members_list_main")

ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호",
    "제품명", "가격", "PV", "결재방법",
    "주문고객명", "주문자_휴대폰번호", "배송처", "수령확인"
]

BONUS_REQUIRED_HEADERS = {"기준일자", "합계_좌", "합계_우", "취득점수", "관리자직급"}

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

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    return gspread.authorize(creds)

def get_members_sheet():
    return get_client().open("DB").worksheet("DB")

def get_order_sheet():
    client = get_client()
    ss = client.open("제품주문")
    try:
        sheet = ss.worksheet("제품주문")
    except:
        sheet = ss.add_worksheet(title="제품주문", rows="1000", cols="20")
    if not any(sheet.row_values(1)):
        sheet.append_row(ORDER_HEADERS)
    return sheet

def get_bonus_sheet():
    client = get_client()
    ss = client.open("후원수당파일")
    try:
        return ss.worksheet("후원수당파일")
    except:
        return ss.add_worksheet(title="후원수당파일", rows="1000", cols="50")

@app.route("/")
def index():
    return jsonify({"message": "Flask 서버가 정상 작동 중입니다."})

@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("name", "").strip()

        if not name:
            return jsonify({"error": "이름을 입력해야 합니다."}), 400

        sheet = get_members_sheet()
        db_records = sheet.get_all_records()
        member_info = next((r for r in db_records if r.get("회원명") == name), None)

        if not member_info:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

        fields = [
            "회원명", "휴대폰번호", "회원번호", "비밀번호", "가입일자", "생년월일", "통신사", "친밀도", "근무처", "계보도",
            "소개한분", "주소", "메모", "코드", "카드사", "카드주인", "카드번호", "유효기간", "비번", "카드생년월일",
            "분류", "회원단계", "연령/성별", "직업", "가족관계", "니즈", "애용제품", "콘텐츠", "습관챌린지",
            "비즈니스시스템", "GLC프로젝트", "리더님", "NO"
        ]

        result = {field: member_info.get(field, "") for field in fields}
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

from flask import render_template




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # ✅ Render에서 감지 가능한 포트


