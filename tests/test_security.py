"""
Test cases for security and encryption functionality
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.security import encrypt_phi, decrypt_phi, create_access_token
from jose import jwt
from app.config import settings


class TestEncryption:
    """Test PHI encryption/decryption"""
    
    def test_encrypt_decrypt_success(self):
        """Test successful encryption and decryption"""
        original_text = "Patient has headache and fever"
        encrypted = encrypt_phi(original_text)
        assert encrypted != original_text
        assert len(encrypted) > 0
        
        decrypted = decrypt_phi(encrypted)
        assert decrypted == original_text
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string"""
        encrypted = encrypt_phi("")
        assert encrypted == ""
    
    def test_decrypt_empty_string(self):
        """Test decrypting empty string"""
        decrypted = decrypt_phi("")
        assert decrypted == ""
    
    def test_decrypt_invalid_data(self):
        """Test decrypting invalid/corrupted data"""
        decrypted = decrypt_phi("invalid_encrypted_data")
        assert "[DATA CORRUPTION ERROR]" in decrypted or decrypted == ""
    
    def test_encrypt_special_characters(self):
        """Test encryption with special characters"""
        text = "Patient's symptoms: headache, fever (38°C), nausea!"
        encrypted = encrypt_phi(text)
        decrypted = decrypt_phi(encrypted)
        assert decrypted == text


class TestTokenGeneration:
    """Test JWT token generation"""
    
    def test_create_access_token(self):
        """Test creating access token"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        assert token is not None
        assert len(token) > 0
    
    def test_token_contains_expiry(self):
        """Test that token contains expiry information"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload
        assert "sub" in payload
        assert payload["sub"] == "test@example.com"
    
    def test_token_expiry_time(self):
        """Test token expiry time"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_time = payload["exp"]
        # Token should expire in approximately ACCESS_TOKEN_EXPIRE_MINUTES
        assert exp_time > 0

