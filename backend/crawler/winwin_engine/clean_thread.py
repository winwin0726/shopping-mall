from PyQt5.QtCore import QThread, pyqtSignal
import os
import shutil
import time
import json
import glob

class CleanThread(QThread):
    """정리 작업을 처리하는 스레드"""
    
    # 신호 정의
    progress_signal = pyqtSignal(int, str)  # 진행률, 메시지
    log_signal = pyqtSignal(str)  # 로그 메시지
    finished_signal = pyqtSignal(bool, float, str)  # 성공 여부, 정리된 크기(MB), 메시지
    
    def __init__(self, profile_dir, clean_mode="normal"):
        super().__init__()
        self.profile_dir = profile_dir
        self.clean_mode = clean_mode  # "light", "normal", "deep"
        self.is_cancelled = False
    
    def run(self):
        """스레드 실행"""
        try:
            # 시작 시간 기록
            start_time = time.time()
            
            # 진행 상황 업데이트
            self.progress_signal.emit(5, "정리 준비 중...")
            self.log_signal.emit("정리 작업 시작")
            
            # 프로필 디렉토리가 있는지 확인
            if not os.path.exists(self.profile_dir):
                self.log_signal.emit("정리할 프로필 디렉토리가 존재하지 않습니다.")
                self.finished_signal.emit(False, 0, "정리할 프로필 디렉토리가 존재하지 않습니다.")
                return
            
            # 정리 전 크기 계산
            self.progress_signal.emit(10, "프로필 크기 계산 중...")
            before_size = self.get_dir_size(self.profile_dir)
            self.log_signal.emit(f"정리 전 프로필 크기: {before_size / (1024 * 1024):.2f}MB")
            
            # 정리 모드에 따른 처리
            if self.clean_mode == "light":
                self.progress_signal.emit(20, "가벼운 정리 모드 실행 중...")
                self.log_signal.emit("가벼운 정리 모드 실행 중...")
                self._light_clean()
            elif self.clean_mode == "deep":
                self.progress_signal.emit(20, "강력 정리 모드 실행 중...")
                self.log_signal.emit("강력 정리 모드 실행 중...")
                self._deep_clean()
            else:  # normal
                self.progress_signal.emit(20, "일반 정리 모드 실행 중...")
                self.log_signal.emit("일반 정리 모드 실행 중...")
                self._normal_clean()
            
            # 정리 후 크기 계산
            self.progress_signal.emit(90, "정리 후 크기 계산 중...")
            after_size = self.get_dir_size(self.profile_dir)
            cleaned_size = (before_size - after_size) / (1024 * 1024)
            
            # 정리 통계 로깅
            self.progress_signal.emit(95, "정리 통계 기록 중...")
            log_file = os.path.join(self.profile_dir, "cleanup_stats.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "elapsed_time": f"{time.time() - start_time:.2f}초",
                    "before_size_mb": f"{before_size / (1024 * 1024):.2f}",
                    "after_size_mb": f"{after_size / (1024 * 1024):.2f}",
                    "cleaned_size_mb": f"{cleaned_size:.2f}",
                    "clean_mode": self.clean_mode
                }, f, ensure_ascii=False, indent=4)
            
            # 소요 시간 계산
            elapsed_time = time.time() - start_time
            
            # 완료 신호 발생
            self.progress_signal.emit(100, "정리 완료")
            self.log_signal.emit(f"정리 완료: {cleaned_size:.2f}MB 정리됨 (소요시간: {elapsed_time:.2f}초)")
            self.finished_signal.emit(True, cleaned_size, f"프로필 정리 완료: {cleaned_size:.2f}MB 정리됨 (소요시간: {elapsed_time:.2f}초)")
        
        except Exception as e:
            self.log_signal.emit(f"정리 중 오류 발생: {str(e)}")
            self.finished_signal.emit(False, 0, f"정리 중 오류 발생: {str(e)}")
    
    def _light_clean(self):
        """가벼운 정리 모드 - 캐시 폴더만 정리"""
        # 캐시 폴더만 정리
        cache_folders = [
            'Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'Service Worker',
            'Default\\Cache', 'Default\\Code Cache', 'Default\\GPUCache', 'Default\\ShaderCache',
            'Default\\Service Worker'
        ]
        
        total_folders = len(cache_folders)
        for i, folder in enumerate(cache_folders):
            # 작업 취소 확인
            if self.is_cancelled:
                self.log_signal.emit("정리 작업이 취소되었습니다.")
                return
            
            # 진행률 업데이트 (20%~80%)
            progress = 20 + int(60 * ((i + 1) / total_folders))
            self.progress_signal.emit(progress, f"캐시 폴더 정리 중... ({i+1}/{total_folders})")
            
            folder_path = os.path.join(self.profile_dir, folder)
            if os.path.exists(folder_path):
                try:
                    self.log_signal.emit(f"폴더 정리 중: {folder}")
                    shutil.rmtree(folder_path)
                    os.makedirs(folder_path, exist_ok=True)
                except Exception as e:
                    self.log_signal.emit(f"폴더 정리 중 오류: {folder} - {str(e)}")
    
    def _normal_clean(self):
        """일반 정리 모드 - 캐시 및 임시 파일 삭제"""
        # 정리할 폴더 목록 (대용량 캐시 및 불필요 데이터)
        clean_folders = [
            'Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'Service Worker', 'DawnCache',
            'GrShaderCache', 'IndexedDB', 'blob_storage', 'VideoDecodeStats', 'Safe Browsing',
            'SafetyTips', 'WebRTC Logs', 'Sessions', 'shared_proto_db', 'Extensions',
            'File System', 'Storage', 'Application Cache', 'databases', 'Network',
            'Network Action Predictor', 'Reporting and NEL', 'Sync Data', 'Top Sites',
            'Visited Links', 'Web Applications', 'WebStorage', 'Favicons', 'Thumbnails',
            'JumpListIcons', 'JumpListIconsOld', 'Feature Engagement Tracker', 'BrowserMetrics',
            'Shortcuts', 'Affiliation Database', 'data_reduction_proxy_leveldb',
            'Extension Rules', 'Extension State', 'Sync App Settings', 'Sync Extension Settings',
            'Sync FileSystem', 'GCM Store', 'Local Extension Settings', 'Managed Extension Settings',
            'Sync Extension Settings', 'Sync Data', 'temp', 'Temp', 'TMP', 'tmp', 'CacheStorage',
            'ChromeDWriteFontCache', 'Default\\Storage', 'Default\\File System', 'Default\\IndexedDB',
            'Default\\Cache', 'Default\\Code Cache', 'Default\\Service Worker', 'Default\\GPUCache',
            'Default\\DawnCache', 'Default\\blob_storage', 'Default\\VideoDecodeStats',
            'Default\\WebStorage', 'Default\\Sessions', 'Default\\shared_proto_db',
            'Default\\Extension State', 'Default\\Extensions', 'Default\\Local Extension Settings',
            'Default\\Sync Extension Settings', 'Default\\Platform Notifications',
            'Default\\optimization_guide_model_store', 'Default\\OptimizationHints',
            'Default\\OriginTrials', 'Default\\ShaderCache', 'Default\\GrShaderCache',
            'Default\\IndexedDB', 'Default\\Safe Browsing', 'Default\\SafetyTips',
            'Default\\RecoveryImproved', 'Default\\segmentation_platform', 'Default\\screen_ai',
            'Default\\PKIMetadata', 'Default\\PnaclTranslationCache', 'Default\\DownloadMetadata',
            'Default\\Download Service', 'Default\\BudgetDatabase', 'Default\\AutofillStrikeDatabase',
            'Default\\heavy_ad_intervention_opt_out', 'Default\\WebRTC Logs'
        ]
        
        # 삭제할 파일 패턴 (대용량 파일 및 임시 파일)
        delete_patterns = [
            '*.tmp', '*.temp', '*.log', '*.old', '*.bak', '*.dmp',
            'Crashpad', 'crash_reports', '*.dump', 'minidump',
            'Default\\*.tmp', 'Default\\*.temp', 'Default\\*.log', 'Default\\*.old',
            'Default\\*.bak', 'Default\\*.dmp', 'Default\\Crashpad', 'Default\\crash_reports',
            'Default\\*.dump', 'Default\\minidump', '*.ldb', '*.sst', 'CURRENT', 'LOCK',
            'LOG', 'LOG.old', 'MANIFEST-*', '*.log.*', 'Default\\*.ldb', 'Default\\*.sst',
            'Default\\CURRENT', 'Default\\LOCK', 'Default\\LOG', 'Default\\LOG.old',
            'Default\\MANIFEST-*', 'Default\\*.log.*'
        ]
        
        # 1. 폴더 정리
        total_folders = len(clean_folders)
        for i, folder in enumerate(clean_folders):
            # 작업 취소 확인
            if self.is_cancelled:
                self.log_signal.emit("정리 작업이 취소되었습니다.")
                return
            
            # 진행률 업데이트 (20%~50%)
            progress = 20 + int(30 * ((i + 1) / total_folders))
            self.progress_signal.emit(progress, f"폴더 정리 중... ({i+1}/{total_folders})")
            
            folder_path = os.path.join(self.profile_dir, folder)
            if os.path.exists(folder_path):
                try:
                    self.log_signal.emit(f"폴더 정리 중: {folder}")
                    shutil.rmtree(folder_path)
                    os.makedirs(folder_path, exist_ok=True)
                except Exception as e:
                    self.log_signal.emit(f"폴더 정리 중 오류: {folder} - {str(e)}")
        
        # 2. 파일 패턴 정리
        total_patterns = len(delete_patterns)
        for i, pattern in enumerate(delete_patterns):
            # 작업 취소 확인
            if self.is_cancelled:
                self.log_signal.emit("정리 작업이 취소되었습니다.")
                return
            
            # 진행률 업데이트 (50%~70%)
            progress = 50 + int(20 * ((i + 1) / total_patterns))
            self.progress_signal.emit(progress, f"파일 패턴 정리 중... ({i+1}/{total_patterns})")
            
            self.log_signal.emit(f"파일 패턴 정리 중: {pattern}")
            for file_path in glob.glob(os.path.join(self.profile_dir, pattern), recursive=True):
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        self.log_signal.emit(f"파일 삭제 중 오류: {file_path} - {str(e)}")
        
        # 3. 대용량 파일 정리 (10MB 이상)
        self.progress_signal.emit(70, "대용량 파일 정리 중...")
        self.log_signal.emit("대용량 파일 정리 중...")
        
        for root, dirs, files in os.walk(self.profile_dir):
            # 작업 취소 확인
            if self.is_cancelled:
                self.log_signal.emit("정리 작업이 취소되었습니다.")
                return
            
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # 중요 파일 제외
                    if any(important in file_path for important in ['Cookies', 'Login Data', 'Web Data', 'Preferences', 'Secure Preferences', 'Local State']):
                        continue
                    
                    # 대용량 파일 확인 (10MB 이상)
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 10 * 1024 * 1024:
                        self.log_signal.emit(f"대용량 파일 삭제: {file_path}")
                        os.remove(file_path)
                except Exception as e:
                    self.log_signal.emit(f"대용량 파일 삭제 중 오류: {file_path} - {str(e)}")
    
    def _deep_clean(self):
        """강력 정리 모드 - 모든 불필요 파일 삭제 (로그인 정보 유지)"""
        # 중요 파일 백업
        self.progress_signal.emit(20, "중요 파일 백업 중...")
        self.log_signal.emit("중요 파일 백업 중...")
        
        important_files = ['Cookies', 'Login Data', 'Web Data', 'Preferences', 'Secure Preferences', 'Local State']
        temp_dir = os.path.join(os.path.dirname(self.profile_dir), "temp_important_files")
        
        # 임시 디렉토리 생성
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        # 중요 파일 찾아서 백업
        for root, dirs, files in os.walk(self.profile_dir):
            for file in files:
                if any(important in file for important in important_files):
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, self.profile_dir)
                    dst_dir = os.path.join(temp_dir, os.path.dirname(rel_path))
                    os.makedirs(dst_dir, exist_ok=True)
                    dst_path = os.path.join(temp_dir, rel_path)
                    shutil.copy2(src_path, dst_path)
                    self.log_signal.emit(f"중요 파일 백업: {rel_path}")
        
        # 프로필 폴더 초기화
        self.progress_signal.emit(50, "프로필 폴더 초기화 중...")
        self.log_signal.emit("프로필 폴더 초기화 중...")
        
        shutil.rmtree(self.profile_dir)
        os.makedirs(self.profile_dir, exist_ok=True)
        
        # 중요 파일 복원
        self.progress_signal.emit(70, "중요 파일 복원 중...")
        self.log_signal.emit("중요 파일 복원 중...")
        
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, temp_dir)
                dst_dir = os.path.join(self.profile_dir, os.path.dirname(rel_path))
                os.makedirs(dst_dir, exist_ok=True)
                dst_path = os.path.join(self.profile_dir, rel_path)
                shutil.copy2(src_path, dst_path)
                self.log_signal.emit(f"중요 파일 복원: {rel_path}")
        
        # 임시 폴더 삭제
        self.progress_signal.emit(80, "임시 폴더 삭제 중...")
        shutil.rmtree(temp_dir)
    
    def cancel(self):
        """정리 작업 취소"""
        self.is_cancelled = True
    
    def get_dir_size(self, path):
        """디렉토리 크기 계산"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        return total_size
