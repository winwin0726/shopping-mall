import os
import zipfile

def create_project_backup():
    # Source directory (current directory)
    src_dir = r"d:\안티그래비티\winwin크롤러2"
    
    # Destination zip file on Desktop (Prefer OneDrive Desktop if exists)
    onedrive_desktop = r"D:\onedrive\바탕 화면"
    local_desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    desktop_path = onedrive_desktop if os.path.exists(onedrive_desktop) else local_desktop
    zip_filename = os.path.join(desktop_path, "Winwin_Crawler_v3.3_Backup.zip")
    
    # Directories and files to exclude to keep the zip small and clean
    excludes = {
        '.git', 
        '__pycache__', 
        'node_modules', 
        'build', 
        'dist', 
        'TEMP_CRAWLED', 
        'temp_data_images', 
        'temp_kakao_images', 
        'error_dumps', 
        '__pyrefly_virtual__'
    }
    
    print(f"[Backup] 압축을 시작합니다... (저장 위치: {zip_filename})")
    print("불필요한 대용량 폴더(캐시, 브라우저 프로필, git 등)는 제외됩니다.")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(src_dir):
            # 기본 제외 폴더 필터링
            dirs[:] = [d for d in dirs if d not in excludes]
            
            # 브라우저 프로필 내부의 찌꺼기(수백MB 캐시)만 정밀 타격하여 제외
            if "profile" in root.lower() or "profiles" in root.lower():
                dirs[:] = [d for d in dirs if d.lower() not in ["cache", "code cache", "optimization_guide_model_store", "service worker", "dawncache", "gpucache"]]
            else:
                # profile 폴더가 아닌 일반 폴더의 경우 cache라는 이름이 있으면 제외
                dirs[:] = [d for d in dirs if "cache" not in d.lower()]
            
            for file in files:
                if file.endswith(('.pyc', '.zip', '.pack', '.idx')) or file == "Winwin_Crawler_v3.3_Backup.zip" or file == ".env":
                    continue
                    
                file_path = os.path.join(root, file)
                # Ensure the path inside the zip is relative to the src_dir
                arcname = os.path.relpath(file_path, src_dir)
                
                try:
                    zipf.write(file_path, arcname)
                except Exception as e:
                    print(f"⚠️ 경고: {arcname} 파일을 압축하는 데 실패했습니다. ({e})")
                    
    print(f"[Done] 백업 완료! 바탕화면에서 '{os.path.basename(zip_filename)}' 파일을 확인하세요.")

if __name__ == "__main__":
    create_project_backup()
