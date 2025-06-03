import MeCab

try:
    mecab = MeCab.Tagger(r'-d C:\mecab\mecab-0.996-ko-0.9.2-e\mecab-ko-dic')
    result = mecab.parse("형태소 분석이 잘 될까요?")
    print("✅ 분석 결과:\n", result)
except Exception as e:
    print("❌ 오류 발생:", e)
