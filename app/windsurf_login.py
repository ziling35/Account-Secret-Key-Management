"""
Windsurf 登录服务模块
通过账号密码登录获取 API Key
"""
import httpx
import os
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import re


class WindsurfLoginService:
    """Windsurf 登录服务"""
    
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    def __init__(self, firebase_api_key: Optional[str] = None, db: Optional[Session] = None):
        """
        初始化登录服务
        
        Args:
            firebase_api_key: Firebase API Key，如果不提供则自动获取
            db: 数据库会话，用于从数据库读取配置
        """
        # 优先级：传入参数 > 环境变量 > 数据库配置
        self.firebase_api_key = firebase_api_key or os.getenv("FIREBASE_API_KEY")
        
        # 如果还没有 API Key，尝试从数据库读取
        if not self.firebase_api_key and db:
            from app.models import Config
            config = db.query(Config).filter(Config.key == "firebase_api_key").first()
            if config:
                self.firebase_api_key = config.value
        
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
    
    async def get_firebase_api_key(self) -> str:
        """
        自动从 Codeium 网站获取 Firebase API Key
        
        Returns:
            Firebase API Key
        
        Raises:
            Exception: 无法获取 API Key
        """
        # 已知的 Firebase API Key（后备方案）
        # 更新日期: 2024-12-09
        FALLBACK_FIREBASE_KEY = 'AIzaSyBSJhvHLwiEeIRuKW7hcJJGUeMUwVHUTQQ'
        
        # 如果环境变量中已配置，直接使用
        if self.firebase_api_key:
            return self.firebase_api_key
        
        urls = [
            'https://codeium.com/profile',
            'https://www.codeium.com/profile',
            'https://codeium.com',
            'https://www.codeium.com'
        ]
        
        for url in urls:
            try:
                response = await self.client.get(
                    url,
                    headers={'User-Agent': self.USER_AGENT},
                    timeout=10.0
                )
                html = response.text
                
                # 检查 HTML 内容
                key_match = re.search(r'AIza[0-9A-Za-z_-]{35}', html)
                if key_match:
                    return key_match.group(0)
                
                # 提取 JS 文件链接
                script_urls = re.findall(r'src=["\'](([^"\']+\.js))["\'"]', html)
                
                # 扫描 JS 文件（最多扫描前 10 个）
                for script_match in script_urls[:10]:
                    js_url = script_match[0]
                    if js_url.startswith('/'):
                        js_url = 'https://codeium.com' + js_url
                    elif not js_url.startswith('http'):
                        js_url = 'https://codeium.com/' + js_url
                    
                    # 只扫描主要的应用代码文件
                    if any(keyword in js_url for keyword in ['main', 'app', 'index', 'chunk']):
                        try:
                            js_response = await self.client.get(
                                js_url,
                                headers={'User-Agent': self.USER_AGENT},
                                timeout=5.0
                            )
                            js_content = js_response.text
                            
                            js_key_match = re.search(r'AIza[0-9A-Za-z_-]{35}', js_content)
                            if js_key_match:
                                return js_key_match.group(0)
                        except:
                            continue
            except Exception as e:
                print(f"获取 Firebase API Key 失败 ({url}): {str(e)}")
                continue
        
        # 如果自动获取失败，使用后备 API Key
        print(f"⚠️ 自动获取 Firebase API Key 失败，使用后备 API Key")
        return FALLBACK_FIREBASE_KEY
    
    async def login_with_firebase(self, email: str, password: str) -> str:
        """
        使用 Firebase 登录
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            Firebase ID Token
        
        Raises:
            Exception: 登录失败
        """
        # 如果没有 API Key，尝试自动获取
        if not self.firebase_api_key:
            self.firebase_api_key = await self.get_firebase_api_key()
        
        try:
            response = await self.client.post(
                f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.firebase_api_key}',
                json={
                    'email': email,
                    'password': password,
                    'returnSecureToken': True,
                },
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', '未知错误')
                
                if error_msg == 'INVALID_PASSWORD':
                    raise Exception('密码错误')
                elif error_msg == 'EMAIL_NOT_FOUND':
                    raise Exception('邮箱未注册')
                else:
                    raise Exception(f'登录失败: {error_msg}')
            
            data = response.json()
            return data['idToken']
        
        except httpx.HTTPError as e:
            raise Exception(f'登录请求失败: {str(e)}')
    
    async def register_user(self, firebase_token: str) -> Dict[str, Any]:
        """
        注册/登录用户并获取 API Key
        
        Args:
            firebase_token: Firebase ID Token
        
        Returns:
            包含用户信息和 API Key 的字典
        
        Raises:
            Exception: 注册失败
        """
        try:
            response = await self.client.post(
                'https://web-backend.windsurf.com/exa.seat_management_pb.SeatManagementService/RegisterUser',
                json={'firebase_id_token': firebase_token},
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': self.USER_AGENT,
                }
            )
            
            if response.status_code != 200:
                # 获取响应体以便调试和错误处理
                error_body = ""
                error_message = ""
                try:
                    error_body = response.text
                    print(f"⚠️ RegisterUser 失败: HTTP {response.status_code}, 响应: {error_body[:500]}")
                    # 尝试解析 JSON 获取具体错误信息
                    error_json = response.json()
                    error_message = error_json.get('message', '') or error_json.get('error', '')
                except:
                    pass
                # 在异常中包含具体错误信息，以便上层代码判断
                raise Exception(f'注册请求失败: HTTP {response.status_code} - {error_message}')
            
            data = response.json()
            
            # 提取 API Key
            api_key = data.get('apiKey') or data.get('api_key')
            if not api_key:
                raise Exception('响应中未找到 API Key')
            
            # 提取用户名
            name = data.get('name') or 'Unknown'
            if name == 'Unknown' and data.get('user'):
                user = data.get('user', {})
                name = (user.get('name') or 
                       user.get('displayName') or 
                       user.get('display_name') or 
                       user.get('username') or 
                       'Unknown')
            
            return {
                'api_key': api_key.strip(),
                'name': name,
                'user_data': data
            }
        
        except httpx.HTTPError as e:
            raise Exception(f'注册请求失败: {str(e)}')
    
    async def get_windsurf_auth_token(self, firebase_token: str) -> str:
        """
        获取 Windsurf Auth Token（备用方法）
        
        Args:
            firebase_token: Firebase ID Token
        
        Returns:
            Windsurf Auth Token
        
        Raises:
            Exception: 获取失败
        """
        try:
            response = await self.client.post(
                'https://web-backend.windsurf.com/exa.seat_management_pb.SeatManagementService/GetOneTimeAuthToken',
                json={'firebase_id_token': firebase_token},
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': self.USER_AGENT,
                }
            )
            
            if response.status_code != 200:
                try:
                    error_body = response.text
                    print(f"⚠️ GetOneTimeAuthToken 失败: HTTP {response.status_code}, 响应: {error_body[:500]}")
                except:
                    pass
                raise Exception(f'获取 Auth Token 失败: HTTP {response.status_code}')
            
            data = response.json()
            auth_token = data.get('authToken') or data.get('auth_token')
            
            if not auth_token:
                raise Exception('响应中未找到 Auth Token')
            
            return auth_token
        
        except httpx.HTTPError as e:
            raise Exception(f'获取 Auth Token 失败: {str(e)}')
    
    async def create_api_key(self, auth_token: str, name: str = None) -> str:
        """
        创建新的 API Key（备用方法）
        
        Args:
            auth_token: Windsurf Auth Token
            name: API Key 名称
        
        Returns:
            新创建的 API Key
        
        Raises:
            Exception: 创建失败
        """
        if not name:
            from datetime import datetime
            name = f'Windsurf-CLI-{int(datetime.now().timestamp())}'
        
        try:
            response = await self.client.post(
                'https://web-backend.windsurf.com/exa.seat_management_pb.SeatManagementService/CreateTeamApiSecret',
                json={
                    'auth_token': auth_token,
                    'name': name,
                    'role': 'admin',
                },
                headers={
                    'Content-Type': 'application/json',
                    'X-Auth-Token': auth_token,
                    'User-Agent': self.USER_AGENT,
                }
            )
            
            if response.status_code != 200:
                try:
                    error_body = response.text
                    print(f"⚠️ CreateTeamApiSecret 失败: HTTP {response.status_code}, 响应: {error_body[:500]}")
                except:
                    pass
                raise Exception(f'创建 API Key 失败: HTTP {response.status_code}')
            
            data = response.json()
            secret = data.get('secret')
            
            if not secret:
                raise Exception('响应中未找到 secret')
            
            return secret
        
        except httpx.HTTPError as e:
            raise Exception(f'创建 API Key 失败: {str(e)}')
    
    async def login_and_get_api_key(self, email: str, password: str) -> Dict[str, Any]:
        """
        完整的登录流程：通过邮箱密码获取 API Key
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            包含 email, password, api_key, name 的字典
        
        Raises:
            Exception: 登录或获取失败
        """
        try:
            # 步骤1: Firebase 登录
            firebase_token = await self.login_with_firebase(email, password)
            
            # 步骤2: 注册用户并获取 API Key
            user_data = await self.register_user(firebase_token)
            
            return {
                'email': email,
                'password': password,
                'api_key': user_data['api_key'],
                'name': user_data['name']
            }
        
        except Exception as e:
            # 如果 RegisterUser 失败，尝试备用方法
            try:
                firebase_token = await self.login_with_firebase(email, password)
                auth_token = await self.get_windsurf_auth_token(firebase_token)
                api_key = await self.create_api_key(auth_token)
                
                return {
                    'email': email,
                    'password': password,
                    'api_key': api_key,
                    'name': email.split('@')[0]  # 使用邮箱前缀作为名称
                }
            except:
                raise e  # 抛出原始错误

    async def get_current_user(self, auth_token: str) -> Dict[str, Any]:
        """
        获取当前用户信息（包含积分）
        
        Args:
            auth_token: Windsurf Auth Token
        
        Returns:
            包含用户信息和积分的字典
        
        Raises:
            Exception: 获取失败
        """
        try:
            response = await self.client.post(
                'https://web-backend.windsurf.com/exa.seat_management_pb.SeatManagementService/GetCurrentUser',
                json={
                    'auth_token': auth_token,
                    'include_subscription': True,
                },
                headers={
                    'Content-Type': 'application/json',
                    'X-Auth-Token': auth_token,
                    'User-Agent': self.USER_AGENT,
                }
            )
            
            if response.status_code != 200:
                raise Exception(f'获取用户信息失败: HTTP {response.status_code}')
            
            return response.json()
        
        except httpx.HTTPError as e:
            raise Exception(f'获取用户信息失败: {str(e)}')

    async def get_credits_info(self, email: str, password: str) -> Dict[str, Any]:
        """
        获取账号积分信息
        
        Args:
            email: 邮箱
            password: 密码
        
        Returns:
            包含积分信息的字典:
            - email: 邮箱
            - name: 用户名
            - user_used_prompt_credits: 用户已用 prompt 积分
            - user_used_flow_credits: 用户已用 flow 积分
            - team_flex_credit_quota: 团队弹性积分配额
            - team_used_flex_credits: 团队已用弹性积分
            - team_used_prompt_credits: 团队已用 prompt 积分
            - team_used_flow_credits: 团队已用 flow 积分
            - plan_info: 套餐信息
        
        Raises:
            Exception: 登录或获取失败
        """
        # 步骤1: Firebase 登录
        firebase_token = await self.login_with_firebase(email, password)
        
        # 步骤2: 获取 Auth Token
        auth_token = await self.get_windsurf_auth_token(firebase_token)
        
        # 步骤3: 获取当前用户信息
        user_data = await self.get_current_user(auth_token)
        
        # 解析用户信息
        user = user_data.get('user', {})
        team = user_data.get('team', {})
        plan_info = user_data.get('planInfo') or user_data.get('plan_info', {})
        subscription = user_data.get('subscription', {})
        
        # 构建返回结果
        result = {
            'email': email,
            'name': user.get('name', email.split('@')[0]),
            'user_used_prompt_credits': user.get('usedPromptCredits') or user.get('used_prompt_credits', 0),
            'user_used_flow_credits': user.get('usedFlowCredits') or user.get('used_flow_credits', 0),
            'team_name': team.get('name', ''),
            'team_flex_credit_quota': team.get('flexCreditQuota') or team.get('flex_credit_quota', 0),
            'team_used_flex_credits': team.get('usedFlexCredits') or team.get('used_flex_credits', 0),
            'team_used_prompt_credits': team.get('usedPromptCredits') or team.get('used_prompt_credits', 0),
            'team_used_flow_credits': team.get('usedFlowCredits') or team.get('used_flow_credits', 0),
            'plan_type': plan_info.get('planType') or plan_info.get('plan_type', 'unknown'),
            'is_pro': user.get('pro', False),
            'raw_data': user_data,  # 原始数据，便于调试
        }
        
        return result


async def windsurf_login(
    email: str, 
    password: str, 
    firebase_api_key: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    便捷函数：通过邮箱密码登录并获取 API Key
    
    Args:
        email: 邮箱
        password: 密码
        firebase_api_key: Firebase API Key（可选）
        db: 数据库会话（可选，用于读取配置）
    
    Returns:
        包含 email, password, api_key, name 的字典
    
    Raises:
        Exception: 登录或获取失败
    """
    service = WindsurfLoginService(firebase_api_key, db)
    try:
        return await service.login_and_get_api_key(email, password)
    finally:
        await service.close()


async def get_account_credits(
    email: str,
    password: str,
    firebase_api_key: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    便捷函数：通过邮箱密码登录并获取账号积分信息
    
    Args:
        email: 邮箱
        password: 密码
        firebase_api_key: Firebase API Key（可选）
        db: 数据库会话（可选，用于读取配置）
    
    Returns:
        包含积分信息的字典
    
    Raises:
        Exception: 登录或获取失败
    """
    service = WindsurfLoginService(firebase_api_key, db)
    try:
        return await service.get_credits_info(email, password)
    finally:
        await service.close()
