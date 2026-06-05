"""이미지 다운로드/FTP 폴더 복사용 유틸"""

from __future__ import annotations

import os
import re
import shutil
import time
from urllib.parse import urlparse

import requests

def download_image(src, filepath, retries: int = 3, timeout: int = 25):
  try:
      r = requests.get(src, timeout=5)
      with open(filepath, "wb") as f:
          f.write(r.content)
      return True
  except Exception as e:
      print(f"Image download error: {src} - {e}")
      return False




def copy_images_to_ftp(product_code, image_files, source_folder, ftp_folder):
  if not os.path.exists(ftp_folder):
      os.makedirs(ftp_folder)
  for idx, original_filename in enumerate(image_files, start=1):
      source_path = os.path.join(source_folder, original_filename)
      new_filename = f"{product_code}_{idx}.jpg"
      dest_path = os.path.join(ftp_folder, new_filename)
      if os.path.exists(source_path):
          shutil.copy2(source_path, dest_path)
          print(f"Copied {source_path} -> {dest_path}")
      else:
          print(f"Source file not found: {source_path}")

########################################
# 12) FTP 업로드 (자동) - 선택 기능
########################################

