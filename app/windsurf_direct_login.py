"""
Windsurf 直接登录模块（实验性）
尝试绕过 Firebase 直接登录
"""
import httpx
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup


class WindsurfDirectLogin:
    """Windsurf 直接登录服务（实验性）"""
    
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    def __init__(self):
        """初始化登录服务"""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={'User-Agent': self.USER_AGENT}
        )
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
    
    async def try_direct_login(self, email: str, password: str) -> Dict[str, Any]:
        """
        尝试直接登录（方法1：模拟浏览器登录）
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            包含 api_key 的字典
        
        Raises:
            Exception: 登录失败
        """
        try:
            # 1. 访问登录页面获取 CSRF token 等
            login_page = await self.client.get('https://windsurf.com/account/login')
            
            # 2. 提取表单参数
            # 这里需要根据实际的登录页面结构来解析
            
            # 3. 提交登录表单
            login_response = await self.client.post(
                'https://windsurf.com/api/auth/login',  # 假设的登录端点
                json={
                    'email': email,
                    'password': password
                },
                headers={
                    'Content-Type': 'application/json',
                    'Origin': 'https://windsurf.com',
                    'Referer': 'https://windsurf.com/account/login'
                }
            )
            
            if login_response.status_code == 200:
                data = login_response.json()
                # 提取 API Key 或 session token
                return data
            else:
                raise Exception(f'登录失败: HTTP {login_response.status_code}')
                
        except Exception as e:
            raise Exception(f'直接登录失败: {str(e)}')
    
    async def try_oauth_flow(self, email: str, password: str) -> Dict[str, Any]:
        """
        尝试 OAuth 流程（方法2：使用 OAuth）
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            包含 api_key 的字典
        
        Raises:
            Exception: 登录失败
        """
        try:
            # 1. 初始化 OAuth 流程
            oauth_init = await self.client.get(
                'https://codeium.com/windsurf/signin',
                params={
                    'response_type': 'token',
                    'client_id': '3GUryQ7ldAeKEuD2obYnppsnmj58eP5u',  # 从错误信息中看到的
                    'redirect_uri': 'windsurf://codeium.windsurf',
                    'prompt': 'login'
                }
            )
            
            # 2. 提交登录凭据
            # 这里需要根据实际的 OAuth 流程来实现
            
            raise Exception('OAuth 流程尚未完全实现')
            
        except Exception as e:
            raise Exception(f'OAuth 登录失败: {str(e)}')
    
    async def try_session_token(self, email: str, password: str) -> Dict[str, Any]:
        """
        尝试使用 Session Token（方法3：直接获取 session）
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            包含 api_key 的字典
        
        Raises:
            Exception: 登录失败
        """
        try:
            # 尝试直接调用 Windsurf 后端的认证接口
            response = await self.client.post(
                'https://web-backend.windsurf.com/auth/login',  # 假设的端点
                json={
                    'email': email,
                    'password': password
                },
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': self.USER_AGENT
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                raise Exception(f'Session 登录失败: HTTP {response.status_code}')
                
        except Exception as e:
            raise Exception(f'Session Token 获取失败: {str(e)}')
    
    async def try_api_key_direct(self, email: str, password: str) -> Dict[str, Any]:
        """
        尝试直接获取 API Key（方法4：直接调用 API）
        
        这个方法尝试跳过所有中间步骤，直接用账号密码换取 API Key
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            包含 api_key 的字典
        
        Raises:
            Exception: 获取失败
        """
        # 尝试的端点列表
        endpoints = [
            'https://web-backend.windsurf.com/api/auth/token',
            'https://web-backend.windsurf.com/api/key/generate',
            'https://api.windsurf.com/v1/auth/login',
            'https://api.codeium.com/auth/login',
        ]
        
        for endpoint in endpoints:
            try:
                response = await self.client.post(
                    endpoint,
                    json={
                        'email': email,
                        'password': password,
                        'grant_type': 'password'
                    },
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': self.USER_AGENT
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # 检查是否包含 API Key
                    if 'api_key' in data or 'apiKey' in data or 'access_token' in data:
                        return data
                        
            except Exception as e:
                continue
        
        raise Exception('所有直接获取方法均失败')


async def windsurf_direct_login(email: str, password: str) -> Dict[str, Any]:
    """
    便捷函数：尝试多种方法直接登录
    
    Args:
        email: 邮箱
        password: 密码
    
    Returns:
        包含 email, password, api_key, name 的字典
    
    Raises:
        Exception: 所有方法均失败
    """
    service = WindsurfDirectLogin()
    
    try:
        # 尝试方法1：直接登录
        try:
            result = await service.try_direct_login(email, password)
            if result.get('api_key') or result.get('apiKey'):
                return {
                    'email': email,
                    'password': password,
                    'api_key': result.get('api_key') or result.get('apiKey'),
                    'name': result.get('name', email.split('@')[0])
                }
        except:
            pass
        
        # 尝试方法2：Session Token
        try:
            result = await service.try_session_token(email, password)
            if result.get('api_key') or result.get('apiKey'):
                return {
                    'email': email,
                    'password': password,
                    'api_key': result.get('api_key') or result.get('apiKey'),
                    'name': result.get('name', email.split('@')[0])
                }
        except:
            pass
        
        # 尝试方法3：直接 API Key
        try:
            result = await service.try_api_key_direct(email, password)
            if result.get('api_key') or result.get('apiKey') or result.get('access_token'):
                api_key = result.get('api_key') or result.get('apiKey') or result.get('access_token')
                return {
                    'email': email,
                    'password': password,
                    'api_key': api_key,
                    'name': result.get('name', email.split('@')[0])
                }
        except:
            pass
        
        # 所有方法都失败
        raise Exception('所有直接登录方法均失败，仍需使用 Firebase 登录')
        
    finally:
        await service.close()
