import gspread

# credentials.json은 서비스 계정 키
gc = gspread.service_account(filename='credentials.json')

# 시트 키 입력
GOOGLE_SHEET_KEY = "1wa1DNixIwckFYyuTAy5Rxlhu0EVg6VlQCatptLkQDxg"

def test_sheet_access():
    try:
        sh = gc.open_by_key(GOOGLE_SHEET_KEY)
        worksheet = sh.sheet1
        data = worksheet.get_all_values()
        print("✅ 시트 연동 성공! 데이터:")
        for row in data:
            print(row)
    except Exception as e:
        print("❌ 시트 연동 실패:", e)

if __name__ == "__main__":
    test_sheet_access()


