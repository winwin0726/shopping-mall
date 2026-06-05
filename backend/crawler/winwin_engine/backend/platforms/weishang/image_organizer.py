"""
웨이상 상품 이미지 스마트 정렬/압축 모듈
- Vision AI(gemini-2.5-flash-lite)로 사진을 색상별 그룹 + 역할(앞/뒤/디테일/사이즈표) 분류
- 카카오스토리 20장 제한에 맞춰 한 상품의 대표 사진 20장을 선별
"""
import json
import re


MAX_IMAGES_PER_POST = 20


def organize_product_images(img_urls: list, translator, safe_ai_call, add_log=None, split_by_color=True) -> list:
    """
    상품 이미지를 AI 분석 후 업로드 가능한 대표 20장 이하로 정렬/압축합니다.
    
    Args:
        img_urls: 원본 이미지 URL/로컬 경로 리스트
        translator: genai.Client 인스턴스
        safe_ai_call: _safe_ai_call 메서드 (재시도 래퍼)
        add_log: 로그 함수 (선택)
        split_by_color: 색상별로 상품을 쪼개어 가등록할지 여부
    
    Returns:
        list[list[str]]: 색상별 혹은 파트별 대표 사진 목록들
    """
    if not add_log:
        add_log = lambda msg, level="INFO": None

    total = len(img_urls)
    if total <= 0:
        return []

    # AI가 없으면 기존 순서를 유지하되 20장 제한은 반드시 지킨다.
    if not translator or not safe_ai_call:
        if total > MAX_IMAGES_PER_POST:
            add_log(f"  📸 [사진 압축] AI 없음 → 기존 순서 기준 대표 {MAX_IMAGES_PER_POST}장만 유지", "WARNING")
            return [img_urls[:MAX_IMAGES_PER_POST]]
        return [img_urls]

    add_log(f"  📸 [스마트 정렬] 사진 {total}장 → AI 색상/역할 분석 후 대표컷 압축 및 색상 분리(색상분리여부={split_by_color})", "INFO")
    
    # ===== AI에게 이미지 분석 요청 =====
    try:
        ai_result = _analyze_images_with_ai(img_urls, translator, safe_ai_call, add_log)
        
        if ai_result and ai_result.get("colors"):
            return _select_by_ai_analysis(img_urls, ai_result, add_log, split_by_color)
        else:
            add_log("  ⚠️ [스마트 정렬] AI 분석 실패 → 기존 순서 기준 20장 압축", "WARNING")
            return _simple_cap(img_urls, add_log)
    except Exception as e:
        add_log(f"  ⚠️ [스마트 정렬] 오류 발생 → 기존 순서 기준 20장 압축: {e}", "WARNING")
        return _simple_cap(img_urls, add_log)


def _analyze_images_with_ai(img_urls, translator, safe_ai_call, add_log):
    """Vision AI로 이미지 색상 그룹 + 역할 분류"""
    
    # 이미지를 AI에 전달 (URL 기반, 최대 40장까지)
    urls_to_analyze = img_urls[:40]
    
    # 이미지 인덱스 목록 생성
    img_list_text = "\n".join([f"[{i}] {url}" for i, url in enumerate(urls_to_analyze)])
    
    prompt = f"""당신은 의류/패션 상품 사진 분석 전문가입니다.
아래 {len(urls_to_analyze)}장의 상품 사진 URL 목록을 분석해주세요.

**분석 규칙:**
1. 사진들을 **색상별로 엄격하게 그룹핑**하세요. 서로 다른 색상(예: 블랙과 화이트, 블루와 옐로우 등)의 상품은 반드시 서로 다른 그룹으로 철저히 분리해야 합니다.
2. **주의:** 동일한 옷인데 조명, 각도, 모델 착용 여부, 상세 클로즈업 등에 의해 사진별로 색감이 미세하게 다르게 보이는 경우(예: 조명 차이로 밝은 파란색과 어두운 파란색으로 보이는 동일 상품)에는 **절대 개별 그룹으로 쪼개지 마시고**, 반드시 하나의 대표 색상 그룹(예: "블루")으로 묶으셔야 합니다. 오직 확연히 서로 다른 색상의 상품 라인업인 경우에만 그룹을 분할하세요.
3. 각 사진의 **역할을 분류**하세요: front(앞면), back(뒷면), detail(디테일/클로즈업), size(사이즈표)
   - **썸네일 가드 규칙:** 옷의 전체적인 정면을 촬영한 착용샷이나 바닥에 예쁘게 펼쳐놓은 사진(front)을 반드시 각 색상별 대표 썸네일로 올바르게 식별하세요. 사이즈표, 라벨, 세탁 탭, 박스 포장, 실밥 디테일 컷은 절대 front/back으로 분류하지 말고 detail 또는 size_chart로 분류하세요.
4. 색상 이름은 한국어로 (예: "블랙", "화이트", "블루")
5. 여러 색상이 혼합되어 있는 경우, 반드시 색상별로 개별 그룹을 만들어 완벽히 분리하세요.
6. 권장 배치 순서는 각 색상 그룹 내에서 front/back → detail → size_chart 순입니다.

**이미지 목록:**
{img_list_text}

**반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):**
```json
{{
  "colors": [
    {{"color": "색상명", "indices": [0,1,2,3], "front": [0,1], "back": [2], "detail": [3]}},
    {{"color": "색상명", "indices": [4,5,6,7], "front": [4,5], "back": [6], "detail": [7]}}
  ],
  "size_chart": [인덱스],
  "total_colors": 2
}}
```"""

    try:
        # 이미지 URL을 Part로 변환하여 Vision AI에 전달
        from google.genai import types
        contents = []
        
        # 첫 번째 이미지 몇 장만 실제 이미지로 전달 (비용 절감)
        # 나머지는 URL 텍스트로만 전달
        for i, url in enumerate(urls_to_analyze[:30]):
            try:
                import os, requests
                contents.append(f"\n--- [이미지 인덱스 {i}] ---")
                if str(url).startswith("http"):
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        contents.append(types.Part.from_bytes(data=r.content, mime_type="image/jpeg"))
                else:
                    if os.path.exists(url):
                        with open(url, "rb") as f:
                            contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
            except:
                pass
        
        contents.append(prompt)
        
        result = safe_ai_call(
            translator,
            contents=contents,
            model='gemini-2.5-flash-lite',
            max_retries=2
        )
        
        if result and result.text:
            # JSON 파싱
            text = result.text.strip()
            # ```json ... ``` 블록 추출
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            # 또는 { ... } 직접 추출
            elif text.startswith('{'):
                pass
            else:
                brace_match = re.search(r'\{.*\}', text, re.DOTALL)
                if brace_match:
                    text = brace_match.group(0)
            
            parsed = json.loads(text)
            color_count = parsed.get("total_colors", len(parsed.get("colors", [])))
            add_log(f"  🎨 [스마트 정렬] AI 분석 완료: {color_count}가지 색상 감지", "SUCCESS")
            return parsed
    except Exception as e:
        add_log(f"  ⚠️ [스마트 정렬] AI 분석 오류: {e}", "WARNING")
    
    return None


def _valid_indices(indices, total):
    out = []
    for idx in indices or []:
        try:
            i = int(idx)
        except Exception:
            continue
        if 0 <= i < total and i not in out:
            out.append(i)
    return out


def _append_unique(target, values, limit=None):
    for value in values or []:
        if value not in target:
            if limit is not None and len(target) >= limit:
                break
            target.append(value)


def _select_by_ai_analysis(img_urls, ai_result, add_log, split_by_color=True):
    """AI 분석 결과를 기반으로 색상별로 사진을 선별하여 20장 이내로 반환한다."""
    total = len(img_urls)
    size_chart = _valid_indices(ai_result.get("size_chart", []), total)
    colors = ai_result.get("colors", [])

    if not colors:
        return _simple_cap(img_urls, add_log)

    if not split_by_color:
        # 모든 색상 그룹의 분류 데이터를 단일 가상 색상 그룹("통합")으로 병합
        combined_cg = {
            "color": "통합",
            "indices": [],
            "front": [],
            "back": [],
            "detail": []
        }
        for cg in colors:
            for k in ["indices", "front", "back", "detail"]:
                for idx in cg.get(k, []):
                    if idx not in combined_cg[k]:
                        combined_cg[k].append(idx)
        colors = [combined_cg]

    # 1. 색상명 기준 병합 처리 (AI 오동작으로 동일 색상을 여러 객체로 리턴하는 현상 방지)
    merged_colors = {}
    for cg in colors:
        color_name = str(cg.get("color", "")).strip().lower()
        if not color_name:
            color_name = "기타"
        
        if color_name not in merged_colors:
            merged_colors[color_name] = {
                "color": cg.get("color", "기타").strip(), # 원래 표기 보존
                "indices": [],
                "front": [],
                "back": [],
                "detail": []
            }
        
        # 순서 및 중복 제거 병합
        for k in ["indices", "front", "back", "detail"]:
            for idx in cg.get(k, []):
                if idx not in merged_colors[color_name][k]:
                    merged_colors[color_name][k].append(idx)
                    
    colors = list(merged_colors.values())

    # Normalize each color group
    normalized = []
    for cg in colors:
        indices = _valid_indices(cg.get("indices", []), total)
        if not indices:
            continue
        normalized.append({
            "color": cg.get("color", ""),
            "indices": indices,
            "front": _valid_indices(cg.get("front", []), total),
            "back": _valid_indices(cg.get("back", []), total),
            "detail": _valid_indices(cg.get("detail", []), total),
            "first": min(indices),
        })

    # Keep original order based on first appearance
    normalized.sort(key=lambda c: c["first"])
    
    # 정렬 및 상세 로깅
    for group in normalized:
        add_log(f"  🎨 [스마트 정렬] 분석 색상 그룹: {group['color']} (사진 {len(group['indices'])}장)", "INFO")

    used = set()
    posts: list[list[str]] = []

    for group in normalized:
        selected: list[int] = []
        
        # [썸네일 가드레일] 0번째 대표 썸네일 선정
        safe_front = []
        for idx in group.get("front", []):
            if idx in size_chart:
                continue
            # 전체 사진 수 대비 마지막 15% 영역(디테일, 라벨 컷 밀집 구역)에 속하는 것은 대표 썸네일에서 제외
            if total > 5 and idx >= int(total * 0.85):
                continue
            safe_front.append(idx)
            
        thumbnail_idx = None
        if safe_front:
            thumbnail_idx = safe_front[0]
        else:
            safe_back = [idx for idx in group.get("back", []) if idx not in size_chart and (total <= 5 or idx < int(total * 0.85))]
            if safe_back:
                thumbnail_idx = safe_back[0]
            else:
                safe_candidates = [idx for idx in group["indices"] if idx not in size_chart and (total <= 5 or idx < int(total * 0.85))]
                if safe_candidates:
                    thumbnail_idx = min(safe_candidates)
                else:
                    other_candidates = [idx for idx in group["indices"] if idx not in size_chart]
                    if other_candidates:
                        thumbnail_idx = min(other_candidates)
                    else:
                        thumbnail_idx = group["indices"][0]

        selected.append(thumbnail_idx)
        
        # Front & back의 나머지 요소들 순차 삽입
        _append_unique(selected, [idx for idx in group.get("front", []) if idx != thumbnail_idx])
        _append_unique(selected, [idx for idx in group.get("back", []) if idx != thumbnail_idx])
        # Detail images
        _append_unique(selected, group.get("detail", []))
        # Fill with remaining images of this color (excluding size chart)
        remaining = [i for i in group["indices"] if i not in selected and i not in size_chart]
        _append_unique(selected, remaining, limit=MAX_IMAGES_PER_POST)
        # Size chart if space permits
        if size_chart:
            _append_unique(selected, size_chart[:1])
        # Trim to limit
        selected = selected[:MAX_IMAGES_PER_POST]
        used.update(selected)
        post_urls = [img_urls[i] for i in selected if 0 <= i < total]
        if post_urls:
            posts.append(post_urls)

    # Handle leftovers not assigned to any color group
    leftover = [i for i in range(total) if i not in used and i not in size_chart]
    if leftover:
        if posts and len(posts[-1]) < MAX_IMAGES_PER_POST:
            space = MAX_IMAGES_PER_POST - len(posts[-1])
            addable = leftover[:space]
            posts[-1].extend([img_urls[i] for i in addable])
            leftover = leftover[space:]
        while leftover:
            chunk = leftover[:MAX_IMAGES_PER_POST]
            posts.append([img_urls[i] for i in chunk])
            leftover = leftover[MAX_IMAGES_PER_POST:]

    # Ensure the size chart appears in at least one post
    if size_chart:
        chart_idx = size_chart[0]
        chart_url = img_urls[chart_idx]
        if not any(chart_url in p for p in posts):
            for p in posts:
                if len(p) < MAX_IMAGES_PER_POST:
                    p.append(chart_url)
                    break
            else:
                posts.append([chart_url])

    add_log(f"  ✅ [스마트 정렬] 색상별 {len(posts)}개의 게시물 생성", "SUCCESS")
    return posts


def _simple_cap(img_urls, add_log):
    """AI 분석 실패 시 기존 순서를 유지하며 20장으로 압축"""
    total = len(img_urls)
    capped = img_urls[:MAX_IMAGES_PER_POST]
    if total > MAX_IMAGES_PER_POST:
        add_log(f"  📸 [단순 압축] {total}장 중 기존 순서 기준 대표 {len(capped)}장만 유지", "INFO")
    return [capped]
