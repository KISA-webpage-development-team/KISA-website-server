import os

REQUEST_TIMEOUT = 10  # seconds

WANTED_CLIENT_ID = os.environ.get('WANTED_API_CLIENT_ID')
WANTED_CLIENT_SECRET = os.environ.get('WANTED_API_CLIENT_SECRET')
WANTED_BASE_URL = 'https://openapi.wanted.jobs/v1'
WANTED_BASE_URL_V2 = 'https://openapi.wanted.jobs/v2'

WANTED_CATEGORY_MAP = {
    'developer': 518,  # 개발
    'business': 507,   # 경영·비즈니스
    'marketing': 523,  # 마케팅·광고
    'design': 511,     # 디자인
    'sales': 530,      # 영업
    'customer_service': 510,  # 고객서비스·리테일
    'hr': 517,         # HR
    'finance': 508,    # 금융
    'media': 524,      # 미디어
    'engineering': 513, # 엔지니어링·설계
    'manufacturing': 522, # 제조·생산
    'logistics': 532,  # 물류·무역
    'game': 959,       # 게임 제작
    'security': 10566, # 정보보호
    'medical': 515,    # 의료·제약·바이오
    'education': 10101, # 교육
    'legal': 521,      # 법률·법집행기관
    'food': 10057,     # 식·음료
    'construction': 509, # 건설·시설
    'public': 514,     # 공공·복지
}