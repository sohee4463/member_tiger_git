import os
import json
import pandas as pd
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1

# 환경 변수 로드
load_dotenv()
app = Flask(__name__)

# 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# 주문 시트 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호",
    "제품명", "가격", "PV", "결재방법",
    "주문고객명", "주문자_휴대폰번호", "배송처", "수령확인"
]

# 공통 구글 시트 접근 함수
def get_sheet():
    keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    return client.open("members_list_main").worksheet("DB")

# 자연어 명령에서 수정 섹션 추출
def find_update_section(data):
    for section, keys in UPDATE_KEYS.items():
        for key in keys:
            if key in data:
                return section, data[key]
    return None, None

@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."

# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        if not name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_sheet()
        db = sheet.get_all_values()
        headers, rows = db[0], db[1:]

        for row in rows:
            if row[headers.index("회원명")] == name:
                return jsonify(dict(zip(headers, row))), 200

        return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ 회원 수정
@app.route("/update_member", methods=["POST"])
def update_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        if not name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        section, updates = find_update_section(data)
        if section != "회원" or not updates:
            return jsonify({"error": "유효한 회원 수정 요청이 아닙니다."}), 400

        sheet = get_sheet()
        db = sheet.get_all_values()
        headers, rows = db[0], db[1:]

        for idx, row in enumerate(rows, start=2):
            if row[headers.index("회원명")] == name:
                range_notation = f"A{idx}:{rowcol_to_a1(idx, len(headers))}"
                current_row = sheet.get(range_notation)[0]
                updated_row = current_row[:]
                updated_fields = []

                for key, value in updates.items():
                    if key in headers:
                        col_idx = headers.index(key)
                        if col_idx < len(updated_row):
                            updated_row[col_idx] = value
                        else:
                            updated_row.extend([""] * (col_idx - len(updated_row) + 1))
                            updated_row[col_idx] = value
                        updated_fields.append(key)

                sheet.update(range_notation, [updated_row])
                return jsonify({
                    "status": "success",
                    "updated": True,
                    "name": name,
                    "updated_fields": updated_fields,
                    "message": f"{name} 회원 정보가 수정되었습니다."
                }), 200

        return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ 제품 주문 등록
@app.route("/add_order", methods=["POST"])
def add_order():
    try:
        data = request.get_json()
        member_name = data.get("회원명", "").strip()
        if not member_name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_sheet()
        records = sheet.get_all_records()
        member_info = next((r for r in records if r.get("회원명") == member_name), None)
        if not member_info:
            return jsonify({"error": f"'{member_name}' 회원을 DB에서 찾을 수 없습니다."}), 404

        ss = sheet.spreadsheet
        try:
            order_sheet = ss.worksheet("제품주문")
        except:
            order_sheet = ss.add_worksheet(title="제품주문", rows="1000", cols="20")

        if not order_sheet.get_all_values():
            order_sheet.append_row(ORDER_HEADERS)

        row = [
            data.get("주문일자", ""),
            member_name,
            member_info.get("회원번호", ""),
            member_info.get("휴대폰번호", ""),
            data.get("제품명", ""),
            float(data.get("가격", 0)),
            float(data.get("PV", 0)),
            data.get("결재방법", ""),
            data.get("주문고객명", ""),
            data.get("주문자_휴대폰번호", ""),
            data.get("배송처", ""),
            data.get("수령확인", "")
        ]
        order_sheet.append_row(row)
        return jsonify({"message": "제품주문이 저장되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ 후원수당 정리
@app.route("/trigger_bonus_by_sheet", methods=["POST"])
def trigger_bonus_by_sheet():
    try:
        data = request.get_json()
        command = data.get("명령", "").strip()
        sheet_url = data.get("링크", "").strip()
        member_name = data.get("회원명", "").strip() or "미입력"

        if "후원수당" not in command or not sheet_url:
            return jsonify({"error": "후원수당 명령어가 없거나 링크가 없습니다."}), 400

        keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
        keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
        client = gspread.authorize(creds)

        ss = client.open_by_url(sheet_url)
        sheet = ss.sheet1
        values = sheet.get_all_values()

        try:
            start_idx = next(i for i, row in enumerate(values) if "기준일자" in row)
        except StopIteration:
            return jsonify({"error": "'기준일자' 항목이 포함된 행이 없습니다."}), 400

        headers = values[start_idx]
        data_rows = values[start_idx + 1:]
        df = pd.DataFrame(data_rows, columns=headers)

        df["기준일자"] = pd.to_datetime(df["기준일자"], errors="coerce")
        df["취득점수"] = pd.to_numeric(df["취득점수"], errors="coerce")
        df = df[df["취득점수"] > 0].dropna(subset=["기준일자"])
        df.drop_duplicates(subset=["기준일자"], inplace=True)
        df["횟수"] = (df["취득점수"] // 15).astype(int)

        df["반기"] = df["기준일자"].apply(lambda d: f"{d.year}년 {d.month}월 {'전반기' if d.day <= 15 else '후반기'}")
        합계 = df.groupby("반기")["횟수"].sum().to_dict()
        마지막 = df.groupby("반기")["기준일자"].transform("max") == df["기준일자"]
        df["달성횟수"] = ""
        df.loc[마지막, "달성횟수"] = df.loc[마지막, "반기"].map(lambda k: f"{k} {합계[k]}회")
        df["회원명"] = member_name
        df.drop(columns=["반기"], inplace=True)

        df_final = df[["기준일자", "합계_좌", "합계_우", "취득점수", "관리자직급", "횟수", "달성횟수", "회원명"]]

        try:
            result_sheet = ss.worksheet("후원수당_정리")
        except gspread.exceptions.WorksheetNotFound:
            result_sheet = ss.add_worksheet(title="후원수당_정리", rows="1000", cols="20")

        result_sheet.clear()
        result_sheet.update([df_final.columns.tolist()] + df_final.values.tolist())

        return jsonify({"message": "후원수당 정리 결과가 시트에 저장되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
