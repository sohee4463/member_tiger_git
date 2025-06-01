import os
import json
import pandas as pd
from flask import Flask, request, jsonify, render_template
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime
from functools import lru_cache
import logging



load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

SHEET_NAME = os.getenv("SHEET_NAME", "members_list_main")

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

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    return gspread.authorize(creds)

def get_db_sheet():
    return get_client().open(SHEET_NAME).worksheet("DB")

def get_order_sheet():
    client = get_client()
    ss = client.open(SHEET_NAME)
    try:
        sheet = ss.worksheet("제품주문")
    except:
        sheet = ss.add_worksheet(title="제품주문", rows="1000", cols="20")
    if not any(sheet.row_values(1)):
        sheet.append_row(ORDER_HEADERS)
    return sheet

def get_bonus_sheet():
    client = get_client()
    ss = client.open(SHEET_NAME)
    try:
        return ss.worksheet("후원수당파일")
    except:
        return ss.add_worksheet(title="후원수당파일", rows="1000", cols="50")

@app.route('/')
def index():
    return jsonify({"message": "Flask 서버가 정상 작동 중입니다."})

@app.route("/add_order", methods=["POST"])
def add_order():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "요청 데이터가 없습니다."}), 400

        member_name = data.get("회원명", "").strip()
        product_name = data.get("제품명", "").strip()
        order_date = data.get("주문일자", "").strip()

        if not member_name or not product_name or not order_date:
            return jsonify({"error": "회원명, 제품명, 주문일자는 필수입니다."}), 400

        try:
            if data.get("가격", ""):
                float(data.get("가격"))
            if data.get("PV", ""):
                float(data.get("PV"))
        except ValueError:
            return jsonify({"error": "가격 또는 PV는 숫자여야 합니다."}), 400

        sheet = get_db_sheet()
        db_records = sheet.get_all_records()
        member_info = next((r for r in db_records if r.get("회원명") == member_name), None)
        if not member_info:
            return jsonify({"error": f"'{member_name}' 회원을 DB에서 찾을 수 없습니다."}), 404

        member_number = member_info.get("회원번호", "")
        phone_number = member_info.get("휴대폰번호", "")

        order_sheet = get_order_sheet()
        existing_orders = order_sheet.get_all_records()

        duplicate = next(
            (
                r for r in existing_orders
                if r.get("회원명") == member_name and
                   r.get("제품명") == product_name and
                   r.get("주문일자") == order_date
            ),
            None
        )
        if duplicate:
            return jsonify({"error": "이미 같은 날짜에 동일한 제품이 주문되었습니다."}), 409

        row = [
            order_date,
            member_name,
            member_number,
            phone_number,
            product_name,
            data.get("가격", ""),
            data.get("PV", ""),
            data.get("결재방법", ""),
            data.get("주문고객명", ""),
            data.get("주문자_휴대폰번호", ""),
            data.get("배송처", ""),
            data.get("수령확인", "")
        ]

        if len(row) != len(ORDER_HEADERS):
            app.logger.warning(f"❗ 컬럼 수 불일치: {len(row)} vs {len(ORDER_HEADERS)}")
            return jsonify({"error": "저장할 데이터 형식이 올바르지 않습니다."}), 400

        order_sheet.append_row(row)
        app.logger.info(f"✅ 주문 저장: 회원={member_name}, 제품={product_name}, 일자={order_date}")
        return jsonify({"message": "제품주문이 저장되었습니다."})
    except Exception as e:
        app.logger.error(f"add_order 오류: {e}, 회원명={data.get('회원명', '') if data else ''}")
        return jsonify({"error": "주문 저장 중 오류가 발생했습니다."}), 500

@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "요청 데이터가 없습니다."}), 400

        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "이름을 입력해야 합니다."}), 400

        sheet = get_db_sheet()
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
        return jsonify({field: member_info.get(field, "") for field in fields})
    except Exception as e:
        app.logger.error(f"find_member 오류: {e}")
        return jsonify({"error": "회원 검색 중 오류가 발생했습니다."}), 500

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "엑셀 파일이 포함되지 않았습니다."}), 400

        file = request.files['file']
        filename = file.filename.lower()
        content_type = file.content_type

        if not filename.endswith((".xls", ".xlsx")) or "excel" not in content_type:
            return jsonify({"message": "엑셀 파일 형식만 지원됩니다."}), 400

        df_raw = pd.read_excel(file, header=None)

        header_row = None
        for i in range(2):
            if df_raw.iloc[i].astype(str).str.contains("기준일자").any():
                header_row = i
                break

        if header_row is None:
            return jsonify({"message": "헤더행에 '기준일자'가 포함되지 않았습니다."}), 400

        df = df_raw.iloc[header_row+1:]
        df.columns = df_raw.iloc[header_row]
        df = df.fillna("")

        sheet = get_bonus_sheet()
        sheet.clear()
        sheet.update([df.columns.tolist()] + df.values.tolist())

        return jsonify({"message": f"{len(df)}건 업로드 성공"}), 200
    except Exception as e:
        app.logger.error(f"upload_excel 오류: {e}")
        return jsonify({"message": "엑셀 업로드 중 오류가 발생했습니다."}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # ✅ Render에서 감지 가능한 포트

