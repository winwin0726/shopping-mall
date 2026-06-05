import os

file_path = 'web-ui/src/pages/KakaoPage.jsx'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

target = """        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success') {
            updateModalField('raw_description', data.translated_text);
            if (data.parsed_title) updateModalField('title', data.parsed_title);
            if (data.parsed_sale_price) updateModalField('sale_price', data.parsed_sale_price);
            if (data.parsed_product_code) updateModalField('product_code', data.parsed_product_code);
            setShowPromptModal(false);"""

replacement = """        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success') {
            updateModalField('raw_description', data.translated_text);
            if (data.parsed_title) updateModalField('title', data.parsed_title);
            if (data.parsed_sale_price) updateModalField('sale_price', data.parsed_sale_price);
            if (data.parsed_product_code) updateModalField('product_code', data.parsed_product_code);
            
            // 번역 결과를 DB에 즉각 반영하여 프로그램 재시작 시에도 유지되도록 자동 저장
            const fieldsToSave = [
              { field: 'raw_description', value: data.translated_text },
              { field: 'title', value: data.parsed_title || editModal.product.title },
              { field: 'sale_price', value: data.parsed_sale_price || editModal.product.sale_price },
              { field: 'product_code', value: data.parsed_product_code || editModal.product.product_code }
            ];
            for (const item of fieldsToSave) {
               await fetch('/api/crawled_products', {
                 method: 'PUT',
                 headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify({ index: editModal.index, field: item.field, value: item.value || '' })
               }).catch(e => console.error("Auto-save failed", e));
            }
            
            setShowPromptModal(false);"""

if target in text:
    text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS")
else:
    print("NOT FOUND")
