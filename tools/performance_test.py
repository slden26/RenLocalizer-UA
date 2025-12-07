import time
import sys
import os
sys.path.append(os.getcwd())

from src.core.parser import RenPyParser
from pathlib import Path

def create_large_rpy_files(count=15, lines_per_file=100):
    """Create test .rpy files for performance testing."""
    test_dir = Path('temp_test_files')
    test_dir.mkdir(exist_ok=True)
    
    sample_content = '''label start_{i}:
    e "Bu dosya {i} numaralı test dosyasıdır."
    "Bu satır {j} numaralı test satırıdır."
    menu:
        "Seçenek A":
            e "A seçeneğini seçtiniz."
        "Seçenek B":
            e "B seçeneğini seçtiniz."
    init python:
        test_var = _("Çevrilecek test metni {j}")
        normal_var = "Çevrilmeyecek {j}"
'''
    
    for i in range(count):
        file_content = ""
        for j in range(lines_per_file):
            file_content += sample_content.format(i=i, j=j) + "\n"
        
        file_path = test_dir / f"test_file_{i:02d}.rpy"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
    
    print(f"Created {count} test files with {lines_per_file} lines each")
    return test_dir

def test_performance():
    """Test both sequential and parallel parsing performance."""
    parser = RenPyParser()
    
    # Create test files
    test_dir = create_large_rpy_files(15, 50)
    
    print(f"\nTesting with directory: {test_dir}")
    
    # Test sequential processing
    print("\n🔄 Sequential Processing:")
    start_time = time.time()
    sequential_results = parser.extract_from_directory(test_dir)
    sequential_time = time.time() - start_time
    sequential_count = sum(len(texts) for texts in sequential_results.values())
    
    print(f"⏱️  Time: {sequential_time:.2f} seconds")
    print(f"📄 Files: {len(sequential_results)}")
    print(f"📝 Texts: {sequential_count}")
    
    # Test parallel processing with different worker counts
    for workers in [2, 4, 6]:
        print(f"\n⚡ Parallel Processing ({workers} workers):")
        start_time = time.time()
        parallel_results = parser.extract_from_directory_parallel(test_dir, max_workers=workers)
        parallel_time = time.time() - start_time
        parallel_count = sum(len(texts) for texts in parallel_results.values())
        
        print(f"⏱️  Time: {parallel_time:.2f} seconds")
        print(f"📄 Files: {len(parallel_results)}")
        print(f"📝 Texts: {parallel_count}")
        print(f"🚀 Speedup: {sequential_time/parallel_time:.1f}x")
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)
    print(f"\n🧹 Cleaned up test files")

if __name__ == "__main__":
    test_performance()
