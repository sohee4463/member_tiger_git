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
from flask_cors import CORS  # 🔸 CORS

load_dotenv()
app = Flask(__name__)
CORS(app)  # 🔸 CORS 활성화
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

@app.route("/upload_form", methods=["GET"])
def upload_form():
    return """
    <h3>엑셀 업로드</h3>
    <p>엑셀 파일(.xls, .xlsx)을 업로드하세요.</p>
    <form action="/upload_excel" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".xls,.xlsx">
        <input type="submit" value="업로드">
    </form>
    """

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "엑셀 파일이 포함되지 않았습니다."}), 400

        file = request.files['file']
        filename = file.filename.lower()
        mime_type, _ = mimetypes.guess_type(filename)

        if not filename.endswith((".xls", ".xlsx")) or not mime_type or not mime_type.startswith("application/vnd"):
            return jsonify({"message": "엑셀 파일 형식만 지원됩니다."}), 400

        df_raw = pd.read_excel(file, header=None)
        header_row = None
        for i in range(min(5, len(df_raw))):  # 🔸 유연한 범위
            if df_raw.iloc[i].astype(str).str.contains("기준일자").any():
                header_row = i
                break

        if header_row is None:
            return jsonify({"message": "헤더행에 '기준일자'가 포함되지 않았습니다."}), 400

        df = df_raw.iloc[header_row + 1:]
        df.columns = df_raw.iloc[header_row]
        df = df.fillna("")

        if not BONUS_REQUIRED_HEADERS.issubset(set(df.columns)):  # 🔸 필수 컬럼 체크
            missing = BONUS_REQUIRED_HEADERS - set(df.columns)
            return jsonify({"message": f"누락된 필수 컬럼: {', '.join(missing)}"}), 400

        # 🔹 날짜 형식 필터링 추가
        try:
            df = df[df["기준일자"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")]
        except Exception as e:
            app.logger.warning(f"기준일자 필터링 중 오류: {e}")

        sheet = get_bonus_sheet()
        sheet.clear()
        sheet.update([df.columns.tolist()] + df.values.tolist())

        return jsonify({"message": f"{len(df)}건 업로드 성공"}), 200
    except Exception as e:
        app.logger.exception("upload_excel 오류")  # 🔸 traceback 포함
        return jsonify({"message": "엑셀 업로드 중 오류가 발생했습니다."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
