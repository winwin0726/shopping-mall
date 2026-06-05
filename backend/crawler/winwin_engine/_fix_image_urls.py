"""KakaoPage.jsx의 이미지 URL 생성 로직을 StaticFiles 기반으로 변경"""
import re

with open(r'c:\programing\윈윈크롤러2\web-ui\src\pages\KakaoPage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. getProductFirstImageUrl 함수 앞에 buildImageUrl 헬퍼 삽입
old_helper = "  const getProductFirstImageUrl = (product) => {"
new_code = """  // 로컬 이미지 경로를 브라우저에서 접근 가능한 URL로 변환
  // TEMP_CRAWLED → /static_images/, UPDATE → /static_update/
  const buildImageUrl = (dirOrPath, filename) => {
    let fullPath = filename ? (dirOrPath + '/' + filename) : dirOrPath;
    fullPath = fullPath.replace(/\\\\\\\\/g, '/');
    const tcIdx = fullPath.indexOf('TEMP_CRAWLED/');
    if (tcIdx >= 0) {
      const relative = fullPath.substring(tcIdx + 'TEMP_CRAWLED/'.length);
      return '/static_images/' + encodeURIComponent(relative).replace(/%2F/g, '/');
    }
    const upIdx = fullPath.indexOf('UPDATE/');
    if (upIdx >= 0) {
      const relative = fullPath.substring(upIdx + 'UPDATE/'.length);
      return '/static_update/' + encodeURIComponent(relative).replace(/%2F/g, '/');
    }
    return `/api/image?path=${encodeURIComponent(fullPath)}`;
  };

  const getProductFirstImageUrl = (product) => {"""

if old_helper in content:
    content = content.replace(old_helper, new_code)
    print("1. buildImageUrl 헬퍼 삽입 완료")
else:
    print("ERROR: getProductFirstImageUrl 못 찾음")

# 2. getProductFirstImageUrl 본문을 buildImageUrl 사용으로 변경
old_body = "    return `/api/image?path=${encodeURIComponent(product.local_image_dir + '/' + product.image_files[0])}`;"
new_body = "    return buildImageUrl(product.local_image_dir, product.image_files[0]);"
if old_body in content:
    content = content.replace(old_body, new_body)
    print("2. getProductFirstImageUrl 본문 변경 완료")
else:
    print("ERROR: getProductFirstImageUrl 본문 못 찾음")

# 3. 이미지 뷰어의 썸네일 URL 생성 변경 (3586줄 근처)
old_viewer_thumb = "const imgUrl = `/api/image?path=${encodeURIComponent(imageModal.product.local_image_dir + '/' + file)}`;"
new_viewer_thumb = "const imgUrl = buildImageUrl(imageModal.product.local_image_dir, file);"
if old_viewer_thumb in content:
    content = content.replace(old_viewer_thumb, new_viewer_thumb)
    print("3. 이미지 뷰어 썸네일 URL 변경 완료")
else:
    print("ERROR: 이미지 뷰어 썸네일 URL 못 찾음")

# 4. 이미지 뷰어의 메인 이미지 URL 변경 (3680줄 근처)
old_viewer_main = "src={`/api/image?path=${encodeURIComponent(imageModal.product.local_image_dir + '/' + imageModal.selectedImg)}`}"
new_viewer_main = "src={buildImageUrl(imageModal.product.local_image_dir, imageModal.selectedImg)}"
count4 = content.count(old_viewer_main)
if count4 > 0:
    content = content.replace(old_viewer_main, new_viewer_main)
    print(f"4. 이미지 뷰어 메인 이미지 URL 변경 완료 ({count4}곳)")
else:
    print("ERROR: 이미지 뷰어 메인 이미지 URL 못 찾음")

# 5. 다운로드 URL 변경 (3684줄 근처)
old_download = "const url = `/api/image?path=${encodeURIComponent(imageModal.product.local_image_dir + '/' + imageModal.selectedImg)}`;"
new_download = "const url = buildImageUrl(imageModal.product.local_image_dir, imageModal.selectedImg);"
if old_download in content:
    content = content.replace(old_download, new_download)
    print("5. 다운로드 URL 변경 완료")
else:
    print("ERROR: 다운로드 URL 못 찾음")

# 6. 수정 모달의 이미지 URL 생성 변경 (3300-3304줄 근처)
# 여기는 local_image_paths를 사용하는데, buildImageUrl로 통합
old_modal = """                      let imgUrl = file;
                      if (!file.startsWith('http')) {
                         const basename = file.split('/').pop().split('\\\\').pop();
                         const dir = editModal.product.local_image_dir;
                         imgUrl = `/api/image?path=${encodeURIComponent(dir ? dir + '/' + basename : file)}`;
                      }"""
new_modal = """                      let imgUrl = file;
                      if (!file.startsWith('http')) {
                         const basename = file.split('/').pop().split('\\\\').pop();
                         const dir = editModal.product.local_image_dir;
                         imgUrl = dir ? buildImageUrl(dir, basename) : `/api/image?path=${encodeURIComponent(file)}`;
                      }"""
if old_modal in content:
    content = content.replace(old_modal, new_modal)
    print("6. 수정 모달 이미지 URL 변경 완료")
else:
    print("ERROR: 수정 모달 이미지 URL 못 찾음")

with open(r'c:\programing\윈윈크롤러2\web-ui\src\pages\KakaoPage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n모든 변경 완료!")
