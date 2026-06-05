from PyQt5.QtCore import QThread, pyqtSignal
import os
import shutil
import time
import json
import zipfile
import glob

class BackupThread(QThread):
    """백업 작업을 처리하는 스레드"""
    
    # 신호 정의
    progress_signal = pyqtSignal(int, str)  # 진행률, 메시지
    log_signal = pyqtSignal(str)  # 로그 메시지
    finished_signal = pyqtSignal(bool, float, str)  # 성공 여부, 백업 크기(MB), 메시지
    
    def __init__(self, source_dir, backup_dir, max_file_size=1*1024*1024, analyze_first=True, compress=True):
        super().__init__()
        self.source_dir = source_dir
        self.backup_dir = backup_dir
        self.max_file_size = max_file_size
        self.analyze_first = analyze_first
        self.compress = compress
        self.is_cancelled = False
        # 백업 플래그 파일 경로를 초기화 시점에 정의
        self.flag_file = os.path.join(os.path.dirname(self.backup_dir), "backup_in_progress.flag")
    
    def run(self):
        """스레드 실행"""
        try:
            # 백업 중복 실행 방지를 위한 플래그 파일 확인
            if os.path.exists(self.flag_file):
                # 플래그 파일이 오래된 경우 (30분 이상) 삭제
                file_time = os.path.getmtime(self.flag_file)
                current_time = time.time()
                if current_time - file_time > 1800:  # 30분(1800초)
                    os.remove(self.flag_file)
                    self.log_signal.emit("오래된 백업 플래그 파일을 제거했습니다.")
                else:
                    self.log_signal.emit("이미 백업이 진행 중입니다. 잠시 후 다시 시도하세요.")
                    self.finished_signal.emit(False, 0, "이미 백업이 진행 중입니다.")
                    return
            
            # 백업 시작 플래그 생성
            try:
                with open(self.flag_file, 'w') as f:
                    f.write(str(time.time()))
            except Exception as e:
                self.log_signal.emit(f"백업 플래그 생성 실패: {str(e)}")
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 진행 상황 업데이트
            self.progress_signal.emit(5, "백업 준비 중...")
            self.log_signal.emit("백업 작업 시작")
            
            # 백업 전 프로필 크기 분석
            if self.analyze_first:
                self.progress_signal.emit(10, "프로필 분석 중...")
                self.log_signal.emit("프로필 크기 분석 중...")
                total_size = self.analyze_profile_size()
                self.log_signal.emit(f"프로필 총 크기: {total_size / (1024 * 1024):.2f}MB")
            
            # 백업 디렉토리 확인 - 호출하는 쪽에서 이미 생성했다고 가정
            if not os.path.exists(self.backup_dir):
                self.log_signal.emit("백업 디렉토리가 존재하지 않습니다.")
                self.finished_signal.emit(False, 0, "백업 디렉토리가 존재하지 않습니다.")
                return
            
            # 임시 백업 디렉토리 생성
            self.progress_signal.emit(15, "임시 백업 디렉토리 생성 중...")
            temp_backup_dir = self.backup_dir + "_temp"
            if os.path.exists(temp_backup_dir):
                shutil.rmtree(temp_backup_dir)
            os.makedirs(temp_backup_dir)
            
            # 백업에서 제외할 폴더 목록 (대용량 캐시 및 불필요 데이터)
            exclude_folders = [
                'Cache', 'Code Cache', 'GPUCache', 'Media Cache', 'optimization_guide_model_store',
                'OptimizationHints', 'OriginTrials', 'ShaderCache', 'Service Worker', 'DawnCache',
                'GrShaderCache', 'IndexedDB', 'blob_storage', 'VideoDecodeStats', 'Safe Browsing',
                'SafetyTips', 'RecoveryImproved', 'segmentation_platform', 'screen_ai', 'PKIMetadata',
                'PnaclTranslationCache', 'DownloadMetadata', 'Download Service', 'BudgetDatabase',
                'AutofillStrikeDatabase', 'heavy_ad_intervention_opt_out', 'WebRTC Logs', 'Sessions',
                'shared_proto_db', 'Extensions', 'File System', 'Platform Notifications', 'Storage',
                'Application Cache', 'databases', 'History', 'Network', 'Network Action Predictor',
                'Reporting and NEL', 'Sync Data', 'Top Sites', 'Visited Links', 'Web Applications',
                'WebStorage', 'LOG', 'LOG.old', 'LOCK', 'MANIFEST-*', 'Current*', 'Favicons',
                'History-journal', 'QuotaManager', 'QuotaManager-journal', 'TransportSecurity',
                'Thumbnails', 'Thumbnails-journal', 'JumpListIcons', 'JumpListIconsOld',
                'Feature Engagement Tracker', 'BrowserMetrics', 'Shortcuts', 'Shortcuts-journal',
                'Bookmarks', 'Bookmarks-journal', 'Cookies-journal', 'Login Data-journal',
                'Web Data-journal', 'Affiliation Database', 'Affiliation Database-journal',
                'data_reduction_proxy_leveldb', 'Extension Rules', 'Extension State',
                'Sync App Settings', 'Sync Extension Settings', 'Sync FileSystem', 'GCM Store',
                'Local Extension Settings', 'Managed Extension Settings', 'Sync Extension Settings',
                'Sync Data', 'Sync Data/LevelDB', 'temp', 'temp_*', 'Temp', 'Temp_*', 'TMP', 'TMP_*',
                'tmp', 'tmp_*', 'CacheStorage', 'CacheStorage_*', 'ChromeDWriteFontCache',
                'Default\\Storage', 'Default\\File System', 'Default\\IndexedDB', 'Default\\Cache',
                'Default\\Code Cache', 'Default\\Service Worker', 'Default\\GPUCache',
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
            
            # 백업에 포함할 중요 파일 및 폴더 목록
            include_files = [
                'Cookies', 'Login Data', 'Web Data', 'Preferences', 'Secure Preferences',
                'Local State', 'Default\\Cookies', 'Default\\Login Data', 'Default\\Web Data',
                'Default\\Preferences', 'Default\\Secure Preferences'
            ]
            
            # 백업 통계
            stats = {
                "total_files": 0,
                "copied_files": 0,
                "skipped_folders": 0,
                "skipped_large_files": 0,
                "total_size_original": 0,
                "total_size_backup": 0
            }
            
            # 파일 복사 시작
            self.progress_signal.emit(20, "파일 복사 중...")
            
            # 총 파일 수 계산 (진행률 표시용)
            total_files = 0
            for root, dirs, files in os.walk(self.source_dir):
                total_files += len(files)
            
            # 현재 처리한 파일 수
            processed_files = 0
            
            # 필수 폴더 생성 및 파일 복사
            for root, dirs, files in os.walk(self.source_dir):
                # 작업 취소 확인
                if self.is_cancelled:
                    self.log_signal.emit("백업 작업이 취소되었습니다.")
                    self.cleanup_temp_dir(temp_backup_dir)
                    self.finished_signal.emit(False, 0, "백업 작업이 취소되었습니다.")
                    return
                
                # 상대 경로 계산
                rel_path = os.path.relpath(root, self.source_dir)
                if rel_path == '.':
                    rel_path = ''
                    
                # 제외 폴더 건너뛰기
                skip_folder = False
                for exclude_folder in exclude_folders:
                    if exclude_folder in root.split(os.sep):
                        skip_folder = True
                        stats["skipped_folders"] += 1
                        break
                
                if skip_folder:
                    continue
                    
                # 대상 폴더 생성
                target_dir = os.path.join(temp_backup_dir, rel_path)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                    
                # 파일 복사
                for file in files:
                    # 작업 취소 확인
                    if self.is_cancelled:
                        self.log_signal.emit("백업 작업이 취소되었습니다.")
                        self.cleanup_temp_dir(temp_backup_dir)
                        self.finished_signal.emit(False, 0, "백업 작업이 취소되었습니다.")
                        return
                    
                    stats["total_files"] += 1
                    processed_files += 1
                    
                    # 진행률 업데이트 (20%~70%)
                    progress = 20 + int(50 * (processed_files / total_files)) if total_files > 0 else 50
                    self.progress_signal.emit(progress, f"파일 복사 중... ({processed_files}/{total_files})")
                    
                    # 중요 파일이거나 작은 파일만 복사
                    source_file = os.path.join(root, file)
                    
                    # 파일 크기 확인
                    if os.path.exists(source_file):
                        file_size = os.path.getsize(source_file)
                        stats["total_size_original"] += file_size
                        
                        # 파일이 include_files 목록에 있거나 작은 파일인 경우만 복사
                        is_important = False
                        for important_file in include_files:
                            if important_file in source_file:
                                is_important = True
                                break
                        
                        if is_important or file_size < self.max_file_size:
                            target_file = os.path.join(target_dir, file)
                            shutil.copy2(source_file, target_file)
                            stats["copied_files"] += 1
                            stats["total_size_backup"] += file_size
                        else:
                            stats["skipped_large_files"] += 1
            
            # 백업 압축 (선택 사항)
            if self.compress:
                self.progress_signal.emit(75, "백업 파일 압축 중...")
                self.log_signal.emit("백업 파일 압축 중...")
                
                # 압축 파일 경로
                zip_file_path = self.backup_dir + ".zip"
                
                # 기존 압축 파일 삭제
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
                
                # 압축 시작
                with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_backup_dir):
                        for file in files:
                            # 작업 취소 확인
                            if self.is_cancelled:
                                self.log_signal.emit("백업 작업이 취소되었습니다.")
                                self.cleanup_temp_dir(temp_backup_dir)
                                self.finished_signal.emit(False, 0, "백업 작업이 취소되었습니다.")
                                return
                            
                            file_path = os.path.join(root, file)
                            # 상대 경로 계산
                            rel_path = os.path.relpath(file_path, temp_backup_dir)
                            zipf.write(file_path, rel_path)
                
                # 압축 후 임시 디렉토리 삭제
                self.cleanup_temp_dir(temp_backup_dir)
                
                # 압축 파일 크기 계산
                backup_size = os.path.getsize(zip_file_path) / (1024 * 1024)
                
                # 압축 파일을 백업 디렉토리로 이동
                self.progress_signal.emit(90, "백업 파일 이동 중...")
                shutil.copy2(zip_file_path, os.path.join(self.backup_dir, "band_profile_backup.zip"))
                
                # 백업 통계 로깅
                self.progress_signal.emit(95, "백업 통계 기록 중...")
                log_file = os.path.join(self.backup_dir, "backup_stats.json")
                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "elapsed_time": f"{time.time() - start_time:.2f}초",
                        "original_size_mb": f"{stats['total_size_original'] / (1024 * 1024):.2f}",
                        "backup_size_mb": f"{backup_size:.2f}",
                        "compression_ratio": f"{stats['total_size_original'] / (os.path.getsize(zip_file_path) if os.path.exists(zip_file_path) else 1):.2f}",
                        "stats": stats
                    }, f, ensure_ascii=False, indent=4)
            else:
                # 임시 디렉토리를 백업 디렉토리로 이동
                self.progress_signal.emit(90, "백업 파일 이동 중...")
                if os.path.exists(self.backup_dir):
                    shutil.rmtree(self.backup_dir)
                shutil.move(temp_backup_dir, self.backup_dir)
                
                # 백업 크기 계산 (MB)
                backup_size = self.get_dir_size(self.backup_dir) / (1024 * 1024)
                
                # 백업 통계 로깅
                self.progress_signal.emit(95, "백업 통계 기록 중...")
                log_file = os.path.join(self.backup_dir, "backup_stats.json")
                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "elapsed_time": f"{time.time() - start_time:.2f}초",
                        "original_size_mb": f"{stats['total_size_original'] / (1024 * 1024):.2f}",
                        "backup_size_mb": f"{backup_size:.2f}",
                        "compression_ratio": f"{stats['total_size_original'] / (stats['total_size_backup'] if stats['total_size_backup'] > 0 else 1):.2f}",
                        "stats": stats
                    }, f, ensure_ascii=False, indent=4)
            
            # 소요 시간 계산
            elapsed_time = time.time() - start_time
            
            # 완료 신호 발생
            self.progress_signal.emit(100, "백업 완료")
            self.log_signal.emit(f"백업 완료: {backup_size:.2f}MB (소요시간: {elapsed_time:.2f}초)")
            self.finished_signal.emit(True, backup_size, f"최적화된 백업 완료: {backup_size:.2f}MB (소요시간: {elapsed_time:.2f}초)")
        
        except Exception as e:
            self.log_signal.emit(f"백업 중 오류 발생: {str(e)}")
            self.finished_signal.emit(False, 0, f"백업 중 오류 발생: {str(e)}")
        
        finally:
            # 백업 플래그 제거
            try:
                if os.path.exists(self.flag_file):
                    os.remove(self.flag_file)
                    self.log_signal.emit("백업 플래그 파일 제거 완료")
            except Exception as e:
                self.log_signal.emit(f"백업 플래그 파일 제거 실패: {str(e)}")
    
    def cancel(self):
        """백업 작업 취소"""
        self.is_cancelled = True
        
        # 백업 플래그 파일 제거
        try:
            if os.path.exists(self.flag_file):
                os.remove(self.flag_file)
                self.log_signal.emit("백업 플래그 파일 제거 완료")
        except Exception as e:
            self.log_signal.emit(f"백업 플래그 파일 제거 실패: {str(e)}")
    
    def get_dir_size(self, path):
        """디렉토리 크기 계산"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        return total_size
    
    def analyze_profile_size(self):
        """프로필 디렉토리 크기 분석"""
        total_size = self.get_dir_size(self.source_dir)
        
        # 폴더별 크기 분석
        folder_sizes = {}
        for root, dirs, files in os.walk(self.source_dir):
            # 상대 경로 계산
            rel_path = os.path.relpath(root, self.source_dir)
            if rel_path == '.':
                rel_path = '<root>'
                
            # 현재 폴더 크기 계산
            folder_size = 0
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    folder_size += file_size
                    
                    # 큰 파일 로깅 (1MB 이상)
                    if file_size > 1024 * 1024:
                        self.log_signal.emit(f"큰 파일 발견: {file_path} - {file_size / (1024 * 1024):.2f}MB")
            
            folder_sizes[rel_path] = folder_size
        
        # 크기 순으로 정렬하여 로깅
        sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)
        self.log_signal.emit("폴더별 크기 (내림차순):")
        for folder, size in sorted_folders[:10]:  # 상위 10개만 표시
            if size > 1024 * 1024:  # 1MB 이상인 폴더만 표시
                self.log_signal.emit(f"{folder}: {size / (1024 * 1024):.2f}MB")
        
        return total_size
    
    def cleanup_temp_dir(self, temp_dir):
        """임시 디렉토리 정리"""
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                return True
            except Exception as e:
                self.log_signal.emit(f"임시 디렉토리 정리 중 오류: {str(e)}")
                return False
        return True
