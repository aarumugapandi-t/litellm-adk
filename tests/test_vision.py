import pytest
from litellm_adk.utils.vision import VisionOptimizer

def test_is_ssrf_safe():
    # Valid external URLs should pass (assuming google.com resolves to public IP)
    assert VisionOptimizer.is_ssrf_safe("https://google.com/image.png") is True
    
    # Internal metadata IPs should be blocked
    assert VisionOptimizer.is_ssrf_safe("http://169.254.169.254/latest/meta-data") is False
    
    # Localhost should be blocked
    assert VisionOptimizer.is_ssrf_safe("http://localhost/image.png") is False
    assert VisionOptimizer.is_ssrf_safe("http://127.0.0.1/image.png") is False
    
    # Private IPs should be blocked
    assert VisionOptimizer.is_ssrf_safe("http://10.0.0.1/image.png") is False
    assert VisionOptimizer.is_ssrf_safe("http://192.168.1.1/image.png") is False

def test_ssrf_dns_rebinding_bypass_attempt():
    # Attempting to use a DNS name that resolves locally
    assert VisionOptimizer.is_ssrf_safe("http://localhost:8080/image") is False
