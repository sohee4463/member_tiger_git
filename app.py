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


@app.route("/upload_support_bonus_excel", methods=["POST"])
def upload_support_bonus_excel():
    try:
        file = request.files['file']
        name = request.form.get('name', '')  # 예: "홍길동의 후원수당 파일이야"

        # 🔍 이름 추출
        member_name = ""
        if "후원수당" in name and "의" in name:
            member_name = name.split("의")[0].strip()

        # 📥 엑셀 읽기 (헤더 자동 감지: '주문일자'가 있는 행을 헤더로 설정)
        temp_df = pd.read_excel(file, header=None)
        header_row_idx = temp_df[temp_df.iloc[:, 0] == "주문일자"].index[0]
        df = pd.read_excel(file, header=header_row_idx)

        # 🔎 필요한 컬럼 선택
        target_cols = {}
        for col in df.columns:
            if "주문일자" in str(col): target_cols["주문일자"] = col
            elif "합계" in str(col) and "좌" in str(col): target_cols["합계_좌"] = col
            elif "합계" in str(col) and "우" in str(col): target_cols["합계_우"] = col
            elif "취득점수" in str(col): target_cols["취득점수"] = col
            elif "관리자직급" in str(col): target_cols["관리자직급"] = col

        df = df[[target_cols[k] for k in ["주문일자", "합계_좌", "합계_우", "취득점수", "관리자직급"]]]
        df.columns = ["주문일자", "합계_좌", "합계_우", "취득점수", "관리자직급"]

        # 🔢 계산 및 필터링
        df = df[df["취득점수"] > 0]
        df["횟수"] = (df["취득점수"] // 15).astype(int)
        df["이름"] = member_name
        df["주문일자"] = pd.to_datetime(df["주문일자"]).dt.strftime('%Y-%m-%d')

        # 📤 Google Sheets 저장
        sheet = get_sheet().worksheet("후원수당파일")

        # 🎯 A2부터 저장 (1행 비움)
        values = df[["주문일자", "합계_좌", "합계_우", "취득점수", "관리자직급", "횟수", "이름"]].values.tolist()

        for i, row in enumerate(values):
            sheet.insert_row(row, index=2 + i)

        return jsonify({
            "message": f"{member_name}님의 후원수당 자료가 {len(values)}건 저장되었습니다.",
            "rows": len(values)
        })

    except Exception as e:
        return jsonify({"error": str(e)})



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # ✅ Render에서 감지 가능한 포트

