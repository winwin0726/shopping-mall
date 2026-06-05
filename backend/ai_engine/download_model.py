import os
import urllib.request
import sys

def download_progress(block_num, block_size, total_size):
    read_so_far = block_num * block_size
    if total_size > 0:
        percent = read_so_far * 1e2 / total_size
        s = f"\rDownloading model: {percent:.2f}% ({read_so_far / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB)"
        sys.stdout.write(s)
        sys.stdout.flush()
    else:
        sys.stdout.write(f"\rRead {read_so_far} bytes")

def main():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(backend_dir, "ai_engine", "models", ".u2net")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "u2net.onnx")
    
    url = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
    
    print(f"Target Path: {target_path}")
    if os.path.exists(target_path) and os.path.getsize(target_path) > 100 * 1024 * 1024:
        print("Model already exists and seems complete. Skipping download.")
        return
        
    try:
        print("Starting model download from GitHub...")
        urllib.request.urlretrieve(url, target_path, download_progress)
        print("\nDownload Completed Successfully!")
    except Exception as e:
        print(f"\nDownload Failed: {str(e)}")

if __name__ == "__main__":
    main()
