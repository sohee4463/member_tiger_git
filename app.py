import os
import json
import pandas as pd
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app = Flask(__name__)

# 상단 정의
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호",
    "제품명", "가격", "PV", "결재방법",
    "주문고객명", "주문자_휴대폰번호", "배송처", "수령확인"
]
BONUS_HEADERS = ["기준일자", "합계_좌", "합계_우", "취득점수", "횟수", "달성횟수"]

def get_sheet():
    keyfile_raw = os.getenv("GOOGLE_SHEET_KEY")
    keyfile_dict = json.loads(keyfile_raw)
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    return client.open("members_list_main").worksheet("DB")

@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."

@app.route("/add_order", methods=["POST"])
def add_order():
    try:
        data = request.get_json()
        member_name = data.get("회원명", "").strip()
        if not member_name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_sheet()
        db_records = sheet.get_all_records()
        member_info = next((r for r in db_records if r.get("회원명") == member_name), None)
        if not member_info:
            return jsonify({"error": f"'{member_name}' 회원을 DB에서 찾을 수 없습니다."}), 404

        member_number = member_info.get("회원번호", "")
        phone_number = member_info.get("휴대폰번호", "")

        ss = sheet.spreadsheet
        try:
            order_sheet = ss.worksheet("제품주문")
        except:
            order_sheet = ss.add_worksheet(title="제품주문", rows="1000", cols="20")

        existing = order_sheet.get_all_values()
        if not existing:
            order_sheet.append_row(ORDER_HEADERS)

        row = [
            data.get("주문일자", ""),
            member_name,
            member_number,
            phone_number,   
            data.get("제품명", ""),
            data.get("가격", ""),
            data.get("PV", ""),
            data.get("결재방법", ""),
            data.get("주문고객명", ""),
            data.get("주문자_휴대폰번호", ""),
            data.get("배송처", ""),
            data.get("수령확인", "")
        ]
        order_sheet.append_row(row)
        return jsonify({"message": "제품주문이 저장되었습니다."})
    except Exception as e:
        return jsonify({"error": str(e)})






@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("name", "").strip()

        if not name:
            return jsonify({"error": "이름을 입력해야 합니다."}), 400

        sheet = get_sheet()
        db_records = sheet.get_all_records()
        member_info = next((r for r in db_records if r.get("회원명") == name), None)

        if not member_info:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

        # 전체 컬럼 순서에 맞춰 필요한 정보만 반환
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

@app.route("/add_support_bonus", methods=["POST"])
def add_support_bonus():
    try:
        data = request.get_json()

        # 👤 이름 추출 (예: "홍길동의 후원수당이야")
        name_text = data.get("이름", "").strip()
        member_name = ""
        if "의 후원수당" in name_text:
            member_name = name_text.split("의 후원수당")[0].strip()

        if not member_name:
            return jsonify({"error": "회원명을 추출할 수 없습니다."}), 400

        # ✅ 저장 대상 항목
        base_fields = ["기준일자", "합계_좌", "합계_우", "취득점수", "관리자직급"]
        if any(data.get(field) is None for field in base_fields):
            return jsonify({"error": "필수 항목이 누락되었습니다."}), 400

        # 🔢 횟수 계산: 취득점수 15점당 1회
        try:
            score = int(data.get("취득점수"))
            count = score // 15
        except:
            return jsonify({"error": "취득점수는 숫자여야 합니다."}), 400

        # 📤 스프레드시트 저장
        sheet = get_sheet().spreadsheet
        try:
            ws = sheet.worksheet("후원수당파일")
        except:
            ws = sheet.add_worksheet(title="후원수당파일", rows="1000", cols="20")

        existing = ws.get_all_values()
        if not existing or all(cell == '' for cell in existing[0]):
            # 1행 비워두기 (헤더 없이)
            ws.update("A1:G1", [[""]])

        # A2부터 append
        row = [
            data.get("기준일자", ""),
            data.get("합계_좌", ""),
            data.get("합계_우", ""),
            data.get("취득점수", ""),
            data.get("관리자직급", ""),
            count,
            member_name
        ]
        ws.insert_row(row, index=2)

        return jsonify({"message": "후원수당 정보가 저장되었습니다."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # ✅ Render에서 감지 가능한 포트

