import os
import json
import shutil

########################################
# 크롬 프로필을 관리하는 클래스
########################################
class ProfileManager:

    def __init__(self, base_dir="chrome_profiles"):
        """
        초기화
        
        Args:
            base_dir (str): 프로필을 저장할 기본 디렉토리
        """
        self.base_dir = base_dir
        self.profiles = {}
        self.profile_file = "profile_mapping.json"
        
        # 기본 디렉토리 생성
        os.makedirs(self.base_dir, exist_ok=True)
        
        # 프로필 매핑 로드
        self.load_profile_mapping()
    
    def get_profile_dir(self, account_id):
        """
        계정 ID에 해당하는 프로필 디렉토리 경로 반환
        없으면 새로 생성
        
        Args:
            account_id (str): 계정 ID
            
        Returns:
            str: 프로필 디렉토리 경로
        """
        # 계정 ID에서 유효한 디렉토리 이름 생성
        safe_id = self._get_safe_id(account_id)
        
        # 이미 매핑이 있는지 확인
        if safe_id in self.profiles:
            profile_dir = self.profiles[safe_id]
            
            # 디렉토리가 실제로 존재하는지 확인
            if os.path.exists(profile_dir):
                return profile_dir
        
        # 새 프로필 디렉토리 생성
        profile_dir = os.path.join(self.base_dir, f"profile_{safe_id}")
        os.makedirs(profile_dir, exist_ok=True)
        
        # 매핑 업데이트
        self.profiles[safe_id] = profile_dir
        self.save_profile_mapping()
        
        return profile_dir
    
    def remove_profile(self, account_id):
        """
        계정 ID에 해당하는 프로필 제거
        
        Args:
            account_id (str): 계정 ID
            
        Returns:
            bool: 성공 여부
        """
        safe_id = self._get_safe_id(account_id)
        
        if safe_id in self.profiles:
            profile_dir = self.profiles[safe_id]
            
            # 디렉토리 삭제
            if os.path.exists(profile_dir):
                try:
                    shutil.rmtree(profile_dir)
                except Exception as e:
                    print(f"프로필 디렉토리 삭제 오류: {str(e)}")
                    return False
            
            # 매핑에서 제거
            del self.profiles[safe_id]
            self.save_profile_mapping()
            return True
        
        return False
    
    def clear_all_profiles(self):
        """
        모든 프로필 제거
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 모든 프로필 디렉토리 삭제
            for profile_dir in self.profiles.values():
                if os.path.exists(profile_dir):
                    shutil.rmtree(profile_dir)
            
            # 매핑 초기화
            self.profiles = {}
            self.save_profile_mapping()
            return True
        except Exception as e:
            print(f"모든 프로필 제거 오류: {str(e)}")
            return False
    
    def load_profile_mapping(self):
        """
        프로필 매핑 로드
        """
        mapping_file = os.path.join(self.base_dir, self.profile_file)
        
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    self.profiles = json.load(f)
            except Exception as e:
                print(f"프로필 매핑 로드 오류: {str(e)}")
                self.profiles = {}
        else:
            self.profiles = {}
    
    def save_profile_mapping(self):
        """
        프로필 매핑 저장
        """
        mapping_file = os.path.join(self.base_dir, self.profile_file)
        
        try:
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"프로필 매핑 저장 오류: {str(e)}")
    
    def _get_safe_id(self, account_id):
        """
        계정 ID에서 파일 시스템에 안전한 ID 생성
        
        Args:
            account_id (str): 계정 ID
            
        Returns:
            str: 안전한 ID
        """
        # 이메일 주소에서 @ 및 특수문자 처리
        safe_id = account_id.replace('@', '_at_').replace('.', '_dot_')
        
        # 파일 시스템에 안전하지 않은 문자 제거
        safe_id = ''.join(c for c in safe_id if c.isalnum() or c in '_-')
        
        return safe_id
    
    def get_profile_count(self):
        """
        저장된 프로필 수 반환
        """
        return len(self.profiles)
    
    def get_profile_list(self):
        """
        저장된 프로필 목록 반환
        """
        return list(self.profiles.keys())