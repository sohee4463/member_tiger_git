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

@app.route("/upload_commission_excel", methods=["POST"])
def upload_commission_excel():
    try:
        file = request.files['file']
        df = pd.read_excel(file, header=1)

        columns = []
        for col in df.columns:
            if "기준일자" in str(col):
                columns.append(col)
            elif "합계" in str(col) and "좌" in str(col):
                columns.append(col)
            elif "합계" in str(col) and "우" in str(col):
                columns.append(col)
            elif "취득점수" in str(col):
                columns.append(col)

        df = df[columns]
        df.columns = BONUS_HEADERS[:-2]
        df = df[df['취득점수'] > 0]
        df['횟수'] = (df['취득점수'] // 15).astype(int)
        df['기준일자'] = pd.to_datetime(df['기준일자'])

        def classify_half(date):
            return f"{date.strftime('%Y-%m')}_전반기" if date.day <= 15 else f"{date.strftime('%Y-%m')}_후반기"

        df['분기'] = df['기준일자'].apply(classify_half)
        summary = df.groupby('분기')['횟수'].sum().reset_index()
        summary['달성횟수'] = summary['분기'].apply(
            lambda x: f"{x.split('_')[1]} {int(summary.loc[summary['분기'] == x, '횟수'])}회")

        df['달성횟수'] = ""
        for _, row in summary.iterrows():
            분기명 = row['분기']
            label = row['달성횟수']
            last_idx = df[df['분기'] == 분기명]['기준일자'].idxmax()
            df.loc[last_idx, '달성횟수'] = label

        df = df[BONUS_HEADERS + ['분기']]
        df.drop(columns='분기', inplace=True)
        df['기준일자'] = df['기준일자'].dt.strftime('%Y-%m-%d')

        sheet = get_sheet()
        ss = sheet.spreadsheet
        try:
            bonus_sheet = ss.worksheet("후원수당")
        except:
            bonus_sheet = ss.add_worksheet(title="후원수당", rows="1000", cols="10")

        existing = bonus_sheet.get_all_records()
        existing_dates = {r["기준일자"] for r in existing if "기준일자" in r}
        filtered = df[~df["기준일자"].isin(existing_dates)]

        if not existing:
            bonus_sheet.append_row(BONUS_HEADERS)

        values = filtered.values.tolist()
        if values:
            bonus_sheet.append_rows(values)

        return jsonify({"message": f"{len(values)}건이 '후원수당' 시트에 저장되었습니다."})
    except Exception as e:
        return jsonify({"error": str(e)})

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
    data = request.get_json()
    name = data.get("name")
    return jsonify({
        "name": name,
        "phone": "010-1234-5678",
        "email": "test@example.com"
    })



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # ✅ Render에서 감지 가능한 포트

