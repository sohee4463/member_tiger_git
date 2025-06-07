import os
import json
import re
import pandas as pd
import gspread
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from datetime import datetime
from collections import Counter





# 환경 변수 로드
load_dotenv()
app = Flask(__name__)




# 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# ✅ 주문 항목 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호", "제품명",
    "제품가격", "PV", "결재방법", "주문자_고객명", "주문자_휴대폰번호",
    "배송처", "수령확인"
]




def parse_request(text):
    result = {"회원명": "", "수정목록": []}

    # 회원명 추출
    name_match = re.search(r"^([가-힣]{2,3})", text)
    if not name_match:
        name_match = re.search(r"([가-힣]{2,3})\s*회원[의은는이가]?", text)
    if name_match:
        result["회원명"] = name_match.group(1)

    # 전체 필드
    필드패턴 = r"(회원명|휴대폰번호|회원번호|비밀번호|가입일자|생년월일|통신사|친밀도|근무처|계보도|소개한분|주소|메모|코드|카드사|카드주인|카드번호|유효기간|비번|카드생년월일|분류|회원단계|연령/성별|직업|가족관계|니즈|애용제품|콘텐츠|습관챌린지|비즈니스시스템|GLC프로젝트|리더님)"
    수정_패턴 = re.findall(rf"{필드패턴}\s*(?:은|는|을|를)?\s*([\w가-힣\d\-\.:/@]+)", text)

    for 필드, 값 in 수정_패턴:
        result["수정목록"].append({"필드": 필드, "값": 값})

    return result




# ✅ Google Sheets 연동
def get_worksheet(sheet_name):
    keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    return client.open("members_list_main").worksheet(sheet_name)


@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."


def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_ss_sheet():
    return get_worksheet("후원수당")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_mymemo_sheet():
    return get_worksheet("개인메모")

def get_dailyrecord_sheet():
    return get_worksheet("활동일지")

def get_image_sheet():
    return get_worksheet("사진저장")











# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()

        if not name and not number:
            return jsonify({"error": "회원명 또는 회원번호를 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        db = sheet.get_all_values()
        headers, rows = db[0], db[1:]

        for row in rows:
            row_dict = dict(zip(headers, row))
            if name and row_dict.get("회원명") == name:
                return jsonify(row_dict), 200
            if number and row_dict.get("회원번호") == number:
                return jsonify(row_dict), 200

        return jsonify({"error": "해당 회원 정보를 찾을 수 없습니다."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500





















# ✅ 회원 수정


# ✅ 자연어 기반 회원 수정 API
@app.route("/update_member", methods=["POST"])
def update_member():
    try:
        raw_data = request.data.decode("utf-8")
        data = json.loads(raw_data)
        요청문 = data.get("요청문", "").strip()

        if not 요청문:
            return jsonify({"error": "요청문이 비어 있습니다."}), 400

        parsed = parse_request(요청문)
        name = parsed["회원명"]
        수정목록 = parsed["수정목록"]

        if not name or not 수정목록:
            return jsonify({"error": "회원명 또는 수정 필드를 인식할 수 없습니다."}), 400

        sheet = get_member_sheet()
        db = sheet.get_all_records()

        # 회원명으로 정확히 한 명만 일치하는지 확인
        matching_rows = [i for i, row in enumerate(db) if row.get("회원명") == name]
        if len(matching_rows) == 0:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404
        if len(matching_rows) > 1:
            return jsonify({"error": f"'{name}' 회원이 중복됩니다. 고유한 이름만 지원합니다."}), 400

        row_index = matching_rows[0] + 2  # 헤더 포함 때문에 +2

        # 시트 헤더 처리
        raw_headers = sheet.row_values(1)
        headers = [h.strip().lower() for h in raw_headers]

        # 수정 처리
        for 항목 in 수정목록:
            필드, 값 = 항목["필드"], 항목["값"]
            필드정규화 = 필드.strip().lower()
            if 필드정규화 not in headers:
                return jsonify({"error": f"'{필드}' 필드는 시트에 존재하지 않습니다."}), 400
            col_index = headers.index(필드정규화) + 1
            sheet.update_cell(row_index, col_index, 값)

        return jsonify({"status": "success", "회원명": name, "수정": 수정목록}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    




# ✅ 회원 저장 (신규 또는 기존 덮어쓰기)
@app.route('/save_member', methods=['POST'])
def save_member():
    try:
        req = request.get_json()
        name = req.get("회원명")
        if not name:
            return jsonify({"error": "회원명은 필수입니다"}), 400

        sheet = get_member_sheet()  # ✅ 수정된 부분
        data = sheet.get_all_records()
        headers = sheet.row_values(1)

        # 기존 회원이 있으면 덮어쓰기
        for i, row in enumerate(data):
            if row.get('회원명') == name:
                for key, value in req.items():
                    if key in headers:
                        sheet.update_cell(i + 2, headers.index(key) + 1, value)
                return jsonify({"message": f"기존 회원 '{name}' 정보 수정 완료"})

        # 신규 회원이면 추가
        new_row = [''] * len(headers)
        for key, value in req.items():
            if key in headers:
                new_row[headers.index(key)] = value
        sheet.append_row(new_row)
        return jsonify({"message": f"신규 회원 '{name}' 저장 완료"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500







# ✅ 회원 삭제 API
@app.route('/delete_member', methods=['POST'])
def delete_member():
    try:
        name = request.get_json().get("회원명")
        if not name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        data = sheet.get_all_records()

        for i, row in enumerate(data):
            if row.get('회원명') == name:
                sheet.delete_rows(i + 2)  # 헤더 포함으로 인덱스 +2
                return jsonify({"message": f"'{name}' 회원 삭제 완료"}), 200

        return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

    except Exception as e:
        import traceback
        traceback.print_exc()
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
            data.get("주문자_고객명", ""),
            data.get("주문자_휴대폰번호", ""),
            data.get("배송처", ""),
            data.get("수령확인", "")
        ]
        order_sheet.append_row(row)
        return jsonify({"message": "제품주문이 저장되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ✅ Google Sheets 연동
def get_product_order_sheet():
    keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    return client.open("members_list_main").worksheet("제품주문")

# ✅ 주문일자 처리
def process_order_date(raw_date: str) -> str:
    if not raw_date or raw_date.strip() == "":
        return "=TODAY()"
    raw_date = raw_date.strip()
    if "오늘" in raw_date:
        return "=TODAY()"
    elif "어제" in raw_date:
        return "=TODAY()-1"
    elif "내일" in raw_date:
        return "=TODAY()+1"
    try:
        datetime.strptime(raw_date, "%Y-%m-%d")
        return raw_date
    except ValueError:
        return "=TODAY()"

# ✅ 시트에 주문 삽입
def insert_order_row(order_data):
    sheet = get_product_order_sheet()
    headers = sheet.row_values(1)
    order_data["주문일자"] = process_order_date(order_data.get("주문일자", ""))
    row = [order_data.get(h, "") for h in headers]
    sheet.insert_row(row, index=2)

# ✅ Flask API 라우터
@app.route("/save_order", methods=["POST"])
def save_order():
    try:
        order_data = request.get_json()
        if not order_data:
            return jsonify({"error": "주문 데이터를 입력해 주세요."}), 400
        insert_order_row(order_data)
        return jsonify({"status": "success", "message": "주문이 저장되었습니다."}), 200
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





















def extract_nouns(text):
    return re.findall(r'[가-힣]{2,}', text)

def generate_tags(text):
    nouns = extract_nouns(text)
    top_keywords = [word for word, _ in Counter(nouns).most_common(5)]
    return top_keywords

def find_similar_memos(sheet, tags, limit=5):
    values = sheet.get_all_values()[1:]  # 헤더 제외
    results = []
    for row in values:
        if len(row) < 3:
            continue
        member, date_str, content = row[0], row[1], row[2]
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        memo_tags = extract_nouns(content)
        similarity = len(set(tags) & set(memo_tags))
        if similarity > 0:
            results.append({
                "회원명": member,
                "날짜": date_str,
                "내용": content,
                "일치_태그수": similarity,
                "날짜_obj": parsed_date
            })

    results.sort(key=lambda x: (x["일치_태그수"], x["날짜_obj"]), reverse=True)
    for r in results:
        del r["날짜_obj"]
    return results[:limit]

# 📄 시트 접근 함수 (실제 구현에서는 gspread 등과 연결 필요)
def get_worksheet(name): pass
def get_counseling_sheet(): return get_worksheet("상담일지")
def get_mymemo_sheet(): return get_worksheet("개인메모")
def get_db_sheet(): return get_worksheet("DB")

# ✅ 등록된 회원명 리스트 추출
def get_registered_names():
    db_values = get_db_sheet().get_all_values()
    return [row[0] for row in db_values[1:] if row]

# ✅ 상담일지 등록 명령 판단
def is_counseling_command(text):
    return any(k in text for k in ["상담일지", "상담메모"]) and any(w in text for w in ["기록", "저장", "등록"])

# ✅ 회원명 및 상담내용 추출
def extract_member_and_content(text):
    registered_names = get_registered_names()
    member = "미지정"
    for name in registered_names:
        if name in text:
            member = name
            break
    content_match = re.search(r"상담내용[:：]?\s*(.*)", text)
    if content_match:
        content = content_match.group(1).strip()
    else:
        content = text.split(member, 1)[-1].strip() if member != "미지정" else text
    if not content:
        content = "(상담 내용 없음)"
    return member, content

# ✅ 상담일지 저장 API
@app.route("/add_counseling", methods=["POST"])
def add_counseling():
    data = request.get_json()
    text = data.get("요청문", "")
    mode = data.get("mode", "공유").strip().lower()
    allow_unregistered = data.get("allow_unregistered", False)

    if not text:
        return jsonify({"error": "요청문이 비어 있습니다."}), 400
    if mode not in ["공유", "개인"]:
        return jsonify({"error": "mode 값은 '공유' 또는 '개인'만 가능합니다."}), 400
    if not is_counseling_command(text):
        return jsonify({"message": "상담일지 요청이 아닙니다."}), 200

    member, content = extract_member_and_content(text)
    date = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 미지정 회원일 경우 저장 차단 (옵션)
    if member == "미지정" and not allow_unregistered:
        return jsonify({"error": "회원명을 인식할 수 없습니다. 등록된 회원이 아니면 저장되지 않습니다."}), 400

    # 시트 선택
    sheet = get_mymemo_sheet() if mode == "개인" else get_counseling_sheet()
    if not sheet:
        return jsonify({"error": "시트 접근에 실패했습니다."}), 500

    try:
        sheet.append_row([member, date, content])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"상담일지 저장 실패: {str(e)}"}), 500

    # 응답 생성
    response = {
        "message": f"{member}님의 상담일지가 저장되었습니다.",
        "member": member,
        "mode": mode,
        "date": date,
        "content": content
    }

    # 개인 모드: 태그 및 유사 추천 추가
    if mode == "개인":
        tags = generate_tags(content)
        recommendations = find_similar_memos(sheet, tags, limit=5)
        response["자동_태그"] = tags
        response["유사_상담기록"] = recommendations

    if member == "미지정":
        response["warning"] = "등록된 회원명에서 찾을 수 없어 '미지정'으로 저장되었습니다."

    return jsonify(response), 200










@app.route("/search_memo_by_tags", methods=["POST"])
def search_memo_by_tags():
    try:
        data = request.get_json()
        input_tags = data.get("tags", [])
        limit = int(data.get("limit", 10))
        sort_by = data.get("sort_by", "date").lower()
        min_match = int(data.get("min_match", 1))

        if not input_tags:
            return jsonify({"error": "태그 리스트가 비어 있습니다."}), 400
        if sort_by not in ["date", "tag"]:
            return jsonify({"error": "sort_by는 'date' 또는 'tag'만 가능합니다."}), 400

        sheet = get_mymemo_sheet()
        values = sheet.get_all_values()[1:]  # 헤더 제외
        results = []

        for row in values:
            if len(row) < 3:
                continue
            member, date_str, content = row[0], row[1], row[2]

            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue  # 날짜 형식 오류시 건너뜀

            memo_tags = extract_nouns(content)
            similarity = len(set(input_tags) & set(memo_tags))
            if similarity >= min_match:
                results.append({
                    "회원명": member,
                    "날짜": date_str,
                    "내용": content,
                    "일치_태그수": similarity,
                    "날짜_obj": parsed_date
                })

        # 정렬 조건 적용
        if sort_by == "tag":
            results.sort(key=lambda x: (x["일치_태그수"], x["날짜_obj"]), reverse=True)
        else:  # 기본: 날짜순
            results.sort(key=lambda x: (x["날짜_obj"], x["일치_태그수"]), reverse=True)

        # 날짜 객체 제거
        for r in results:
            del r["날짜_obj"]

        return jsonify({"검색결과": results[:limit]}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500







# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)