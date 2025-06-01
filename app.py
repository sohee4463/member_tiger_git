

import os
import json
import pandas as pd
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime
from gspread.utils import rowcol_to_a1

load_dotenv()
app = Flask(__name__)



# 주문 및 수당 헤더 정의
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호",
    "제품명", "가격", "PV", "결재방법",
    "주문고객명", "주문자_휴대폰번호", "배송처", "수령확인"
]
BONUS_HEADERS = ["기준일자", "합계_좌", "합계_우", "취득점수", "횟수", "달성횟수"]

# Google Sheets 인증
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

# ✅ 제품 주문 등록 API
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

        # 가격과 PV는 숫자형으로 안전하게 변환
        price = float(data.get("가격", 0))
        pv = float(data.get("PV", 0))

        row = [
            data.get("주문일자", ""),
            member_name,
            member_number,
            phone_number,
            data.get("제품명", ""),
            price,
            pv,
            data.get("결재방법", ""),
            data.get("주문고객명", ""),
            data.get("주문자_휴대폰번호", ""),
            data.get("배송처", ""),
            data.get("수령확인", "")
        ]
        order_sheet.append_row(row)
        return jsonify({"message": "제품주문이 저장되었습니다."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ 회원 조회 또는 수정 API
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "이름을 입력해야 합니다."}), 400

        # "수정", "변경", "고쳐" 키워드 중 하나라도 존재하면 수정 처리
        수정데이터 = data.get("수정") or data.get("변경") or data.get("고쳐")

        sheet = get_sheet()
        db_values = sheet.get_all_values()
        headers = db_values[0]
        records = db_values[1:]

        member_index = None
        for idx, row in enumerate(records, start=2):
            if name == row[headers.index("회원명")]:
                member_index = idx
                break

        if member_index is None:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

        if 수정데이터:
            from gspread.utils import rowcol_to_a1
            col_count = len(headers)
            range_notation = f"A{member_index}:{rowcol_to_a1(member_index, col_count)}"
            current_row = sheet.get(range_notation)[0]
            updated_row = current_row[:]

            for key, value in 수정데이터.items():
                if key in headers:
                    col_index = headers.index(key)
                    if col_index < len(updated_row):
                        updated_row[col_index] = value
                    else:
                        updated_row.extend([""] * (col_index - len(updated_row) + 1))
                        updated_row[col_index] = value

            sheet.update(range_notation, [updated_row])
            return jsonify({"message": f"{name} 회원 정보가 수정되었습니다."}), 200

        # 조회 응답
        return jsonify(dict(zip(headers, records[member_index - 2]))), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

