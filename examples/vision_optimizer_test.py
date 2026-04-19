import asyncio
import time
import os
from litellm_adk.utils.vision import VisionOptimizer

async def test_vision_optimization():
    print("--- Vision Optimizer Test ---")
    
    # 1. Test URL fetching and Optimization
    # This is a 2560x1440 image
    image_url = "https://4kwallpapers.com/images/wallpapers/tanjiro-kamado-2560x1440-10054.jpg"
    
    print(f"Loading image for the first time: {image_url}")
    start_time = time.time()
    data_url_1 = await VisionOptimizer.process_image(image_url)
    duration_1 = time.time() - start_time
    
    print(f"First load took: {duration_1:.2f}s")
    print(f"Data URL starts with: {data_url_1[:50]}...")
    print(f"Data URL length: {len(data_url_1)} characters") # Should be relatively small due to resizing

    # 2. Test Caching
    print("\nLoading image for the second time (should be cached)...")
    start_time = time.time()
    data_url_2 = await VisionOptimizer.process_image(image_url)
    duration_2 = time.time() - start_time
    
    print(f"Second load took: {duration_2:.4f}s")
    assert data_url_1 == data_url_2, "Cached data should match exactly"
    assert duration_2 < 0.01, f"Cache hit should be near-instant, but took {duration_2:.4f}s"
    print("OK: Caching verified!")

    # 3. Test SSRF Protection
    print("\nTesting SSRF Protection...")
    bad_url = "http://127.0.0.1/metadata.json"
    result = await VisionOptimizer.process_image(bad_url)
    if result == bad_url:
        print(f"OK: Blocked SSRF URL: {bad_url}")
    else:
        print(f"FAIL: Failed to block SSRF URL: {bad_url}")

    # 4. Test Local File (Creating a dummy file)
    print("\nTesting Local File Processing...")
    mock_file = "non_existent_image.jpg"
    result = await VisionOptimizer.process_image(mock_file)
    assert result == mock_file, "Missing file should return original path"
    print("OK: Local file fallback verified!")

if __name__ == "__main__":
    asyncio.run(test_vision_optimization())
