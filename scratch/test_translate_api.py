import asyncio
import sys
sys.path.insert(0, r"d:\에이전트그룹\LUXAI_ShoppingMall_20260605")

# Windows stdout 인코딩 에러 방지
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding="utf-8")

async def test_translate_api():
    from backend.database import SessionLocal
    from backend.models import HQProduct
    from backend.crawler.ai_translator import AITranslatorPipeline
    from backend.routers.crawler import compute_retail_price
    
    db = SessionLocal()
    try:
        is_mock = False
        product = db.query(HQProduct).filter(HQProduct.id == 47).first()
        if not product:
            print("⚠️ Product 47 not found in DB. Creating a mock product for testing...")
            is_mock = True
            # 가상의 카테고리 생성 및 모킹
            from backend.models import Category
            mock_cat = Category(name="가방", slug="bag", margin_type="percent", margin_value=20.0)
            product = HQProduct(
                id=47,
                kr_name="로에베 가방",
                cn_name="LOEWE BAG",
                kr_description="로에베 가방 官网售价: 22695\n최고급 수입 양가죽으로 제작\n사이즈: 단일 사이즈 (29*19.5*12cm)",
                wholesale_price=0,
                category=mock_cat,
                original_source_url="winwin://moi/bag-loewe-123"
            )
            
        print("=== Before Translation ===")
        print(f"Name: {product.kr_name}")
        print(f"SKU: {product.sku}")
        print(f"Wholesale Price: {product.wholesale_price}")
        print(f"Base Price: {product.base_price}")
        print("=========================\n")
        
        cn_title = product.cn_name or product.kr_name or ""
        cn_desc = product.kr_description or ""
        cat_name = product.category.name if product.category else "의류"
        
        translator = AITranslatorPipeline()
        translated = await translator.translate_product_info(
            cn_title=cn_title,
            cn_desc=cn_desc,
            wholesale_price_krw=product.wholesale_price or 0,
            category_name=cat_name,
            original_source_url=product.original_source_url or ""
        )
        print("Translator output successfully received.")
        
        product.kr_name = translated.get("kr_name") or product.kr_name
        product.kr_description = translated.get("kr_description") or product.kr_description
        product.description_html = translated.get("description_html") or product.description_html
        
        if translated.get("product_code"):
            product.sku = translated.get("product_code")
        if translated.get("sale_price"):
            product.wholesale_price = translated.get("sale_price")
            if product.category:
                product.base_price = compute_retail_price(
                    product.wholesale_price,
                    product.category.margin_type,
                    product.category.margin_value
                )
                
        if not is_mock:
            db.commit()
            db.refresh(product)
        
        print("\n=== After Translation ===")
        print(f"Name: {product.kr_name}")
        print(f"SKU: {product.sku}")
        print(f"Wholesale Price: {product.wholesale_price}")
        print(f"Base Price: {product.base_price}")
        print(f"Description:\n{product.kr_description}")
        print("=========================")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

asyncio.run(test_translate_api())
