# 학습부: 자산복리부 (Wealth Compounding)

분석가 **자산전략가(wealth_strategist)** 가 읽는 자료.

10년·20년·그 이상 살아남으며 자산을 복리로 증식하는 다년 시각. 거시경제·통화·사이클·위기 인식·자산 보존 framework. 단기 시황(거시분석)을 넘어 **장기 생존 + 복리** 가 본질.

## 자료 운영 흐름

- **canon/wealth_compounding/** (이 폴더): "변하지 않는 framework" 의 압축 정제본. LLM 매 호출마다 주입.
- **reference/wealth_compounding/**: 원본 PDF 추출본 (예: 박종훈 강의·전자책). LLM 비주입, RAG 인덱싱 대상.

자료가 점진 추가되는 학습부 (예: 진행 중인 강의). 정제본은 framework 변동 시에만 손글로 갱신, 디테일·시기 전망은 RAG 가 동적으로 retrieve.

자료 채우기는 M2.5 (RAG SPEC + ingest) 와 함께 진행.
