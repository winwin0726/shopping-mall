# -*- coding: utf-8 -*-
import sqlite3
import os

# DB 파일 경로 설정
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "sql_app.db")

print(f"Target DB Path: {_DB_PATH}")

brands_to_add = [
    # 1. 기존 브랜드 (체크용)
    ("샤넬", "Chanel", "chanel"),
    ("루이비통", "Louis Vuitton", "louis-vuitton"),
    ("구찌", "Gucci", "gucci"),
    ("프라다", "Prada", "prada"),
    ("에르메스", "Hermes", "hermes"),
    ("디올", "Dior", "dior"),
    ("보테가베네타", "Bottega Veneta", "bottega-veneta"),
    ("미우미우", "Miu Miu", "miu-miu"),
    ("발렌시아가", "Balenciaga", "balenciaga"),
    ("생로랑", "Saint Laurent", "saint-laurent"),
    ("펜디", "Fendi", "fendi"),
    ("버버리", "Burberry", "burberry"),
    ("고야드", "Goyard", "goyard"),
    ("로에베", "Loewe", "loewe"),
    
    # 2. 가방/지갑 추가 브랜드
    ("셀린느", "Celine", "celine"),
    ("끌로에", "Chloe", "chloe"),
    ("지방시", "Givenchy", "givenchy"),
    ("더로우", "The Row", "the-row"),
    ("로로피아나", "Loro Piana", "loro-piana"),
    ("메종마르지엘라", "Maison Margiela", "maison-margiela"),
    ("델보", "Delvaux", "delvaux"),
    ("알라이아", "Alaia", "alaia"),
    
    # 3. 신발 추가 브랜드
    ("발렌티노", "Valentino", "valentino"),
    ("돌체앤가바나", "Dolce & Gabbana", "dolce-gabbana"),
    ("루부탱", "Christian Louboutin", "christian-louboutin"),
    ("골든구스", "Golden Goose", "golden-goose"),
    ("마크제이콥스", "Marc Jacobs", "marc-jacobs"),
    ("이자벨마랑", "Isabel Marant", "isabel-marant"),
    ("랑방", "Lanvin", "lanvin"),
    ("발리", "Bally", "bally"),
    ("어그", "UGG", "ugg"),
    ("쥬세페", "Giuseppe Zanotti", "giuseppe-zanotti"),
    ("존롭", "John Lobb", "john-lobb"),
    ("톰브라운", "Thom Browne", "thom-browne"),
    ("보스", "BOSS", "boss"),
    ("알렉산더왕", "Alexander Wang", "alexander-wang"),
    ("토즈", "Tod's", "tods"),
    ("디스퀘어드2", "Dsquared2", "dsquared2"),
    ("페라가모", "Salvatore Ferragamo", "ferragamo"),
    ("제냐", "Ermenegildo Zegna", "zegna"),
    ("로저비비에", "Roger Vivier", "roger-vivier"),
    ("몽클레어", "Moncler", "moncler"),
    ("필립플레인", "Philipp Plein", "philipp-plein"),
    ("아르마니", "Giorgio Armani", "armani"),
    
    # 4. 시계 추가 브랜드
    ("오데마피게", "Audemars Piguet", "audemars-piguet"),
    ("벨앤로스", "Bell & Ross", "bell-ross"),
    ("블랑팡", "Blancpain", "blancpain"),
    ("브레게", "Breguet", "breguet"),
    ("브라이틀링", "Breitling", "breitling"),
    ("불가리", "Bvlgari", "bvlgari"),
    ("까르띠에", "Cartier", "cartier"),
    ("쇼파드", "Chopard", "chopard"),
    ("프랭크뮬러", "Franck Muller", "franck-muller"),
    ("위블로", "Hublot", "hublot"),
    ("IWC", "IWC", "iwc"),
    ("예거르쿨트르", "Jaeger-LeCoultre", "jaeger-lecoultre"),
    ("론진", "Longines", "longines"),
    ("몽블랑", "Montblanc", "montblanc"),
    ("파네라이", "Officine Panerai", "panerai"),
    ("오메가", "Omega", "omega"),
    ("파텍필립", "Patek Philippe", "patek-pilippe"),
    ("피아제", "Piaget", "piaget"),
    ("로저드뷔", "Roger Dubuis", "roger-dubuis"),
    ("롤렉스", "Rolex", "rolex"),
    ("태그호이어", "Tag Heuer", "tag-heuer"),
    ("율리스나르덴", "Ulysse Nardin", "ulysse-nardin"),
    ("바쉐론콘스탄틴", "Vacheron Constantin", "vacheron-constantin"),
]

try:
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    
    added_count = 0
    skipped_count = 0
    
    for name, eng_name, slug in brands_to_add:
        # 이미 존재하는 슬러그인지 혹은 영문명인지 체크
        cursor.execute("SELECT id FROM brands WHERE slug = ? OR LOWER(eng_name) = ?", (slug, eng_name.lower()))
        row = cursor.fetchone()
        
        if row:
            skipped_count += 1
        else:
            cursor.execute(
                "INSERT INTO brands (name, eng_name, slug, is_premium, is_active) VALUES (?, ?, ?, 0, 1)",
                (name, eng_name, slug)
            )
            print(f"  └ Added brand: {name} ({eng_name}) -> /brand/{slug}")
            added_count += 1
            
    conn.commit()
    print(f"\n✅ Seeding Complete. Added: {added_count}, Skipped (Already existed): {skipped_count}")
    
except Exception as e:
    print(f"❌ Database error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
