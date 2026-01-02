"""
Windsurf API 调用模块
用于调用Windsurf团队管理相关API，如禁用/启用成员访问权限
"""

import httpx
import struct
from datetime import datetime
from typing import Optional, Tuple

WINDSURF_BASE_URL = "https://web-backend.windsurf.com"


def encode_varint(value: int) -> bytes:
    """编码varint"""
    result = []
    while value > 127:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def encode_string_field(field_num: int, value: str) -> bytes:
    """编码protobuf字符串字段"""
    value_bytes = value.encode('utf-8')
    # wire type 2 (length-delimited) = field_num << 3 | 2
    header = (field_num << 3) | 2
    return bytes([header]) + encode_varint(len(value_bytes)) + value_bytes


def encode_bool_field(field_num: int, value: bool) -> bytes:
    """编码protobuf bool字段"""
    # wire type 0 (varint) = field_num << 3 | 0
    header = (field_num << 3) | 0
    return bytes([header, 1 if value else 0])


async def update_codeium_access(token: str, member_api_key: str, disable_access: bool) -> dict:
    """
    更新成员的 Windsurf 访问权限
    
    Args:
        token: 管理员的Firebase ID Token
        member_api_key: 成员的API Key
        disable_access: True=禁用访问, False=启用访问
    
    Returns:
        dict: {"success": bool, "message": str, ...}
    """
    url = f"{WINDSURF_BASE_URL}/exa.seat_management_pb.SeatManagementService/UpdateCodeiumAccess"
    
    # 构建请求体：auth_token(1) + api_key(2) + disable_codeium_access(3)
    body = encode_string_field(1, token)
    body += encode_string_field(2, member_api_key)
    body += encode_bool_field(3, disable_access)
    
    headers = {
        "accept": "*/*",
        "connect-protocol-version": "1",
        "content-type": "application/proto",
        "x-auth-token": token,
        "Referer": "https://windsurf.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=body, headers=headers)
            
        status_code = response.status_code
        print(f"[UpdateCodeiumAccess] Status: {status_code}, disable={disable_access}, api_key={member_api_key[:20]}...")
        
        if status_code == 200:
            return {
                "success": True,
                "message": "已禁用 Windsurf 访问" if disable_access else "已启用 Windsurf 访问",
                "api_key": member_api_key,
                "disabled": disable_access,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            error_body = response.text
            return {
                "success": False,
                "status_code": status_code,
                "error": "更新访问权限失败",
                "error_details": error_body,
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def get_team_members(token: str, group_id: Optional[str] = None) -> dict:
    """
    获取团队成员列表
    
    Args:
        token: 管理员的Firebase ID Token
        group_id: 可选的组ID
    
    Returns:
        dict: {"success": bool, "members": [...], ...}
    """
    url = f"{WINDSURF_BASE_URL}/exa.seat_management_pb.SeatManagementService/GetTeamMembers"
    
    # 构建请求体：auth_token(1) + group_id(2, optional)
    body = encode_string_field(1, token)
    if group_id:
        body += encode_string_field(2, group_id)
    
    headers = {
        "accept": "*/*",
        "connect-protocol-version": "1",
        "content-type": "application/proto",
        "x-auth-token": token,
        "Referer": "https://windsurf.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=body, headers=headers)
            
        if response.status_code == 200:
            # 解析protobuf响应（简化处理，返回原始数据）
            return {
                "success": True,
                "raw_data": response.content.hex(),
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": "获取成员列表失败",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def get_current_user(token: str) -> dict:
    """
    获取当前用户完整信息（包含 user/team/plan）
    用于获取准确的积分信息
    
    Args:
        token: Firebase ID Token
    
    Returns:
        dict: {
            "success": bool,
            "user": {"used_prompt_credits": int, ...},
            "team": {"used_prompt_credits": int, ...},
            "plan": {"monthly_prompt_credits": int, ...},
            "remaining_credits": int  # 剩余积分
        }
    """
    url = f"{WINDSURF_BASE_URL}/exa.seat_management_pb.SeatManagementService/GetCurrentUser"
    
    # 构建请求体：0x0a + token长度(varint) + token + 0x10 0x01 0x18 0x01 0x20 0x01
    token_bytes = token.encode('utf-8')
    token_length = len(token_bytes)
    
    body = bytearray([0x0a])
    if token_length < 128:
        body.append(token_length)
    else:
        body.append((token_length & 0x7F) | 0x80)
        body.append(token_length >> 7)
    body.extend(token_bytes)
    body.extend([0x10, 0x01, 0x18, 0x01, 0x20, 0x01])
    
    headers = {
        "accept": "*/*",
        "connect-protocol-version": "1",
        "content-type": "application/proto",
        "x-auth-token": token,
        "Referer": "https://windsurf.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=bytes(body), headers=headers)
            
        status_code = response.status_code
        print(f"[GetCurrentUser] Status: {status_code}, size: {len(response.content)} bytes")
        
        if status_code == 200:
            data = response.content
            result = parse_current_user(data)
            result["success"] = True
            result["status_code"] = status_code
            result["timestamp"] = datetime.utcnow().isoformat()
            return result
        else:
            return {
                "success": False,
                "status_code": status_code,
                "error": "获取用户信息失败",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


def parse_current_user(data: bytes) -> dict:
    """
    解析 GetCurrentUser 响应
    提取 user/team/plan 中的积分信息
    
    结构：
    - User (field 1): int_28 = used_prompt_credits
    - Team (field 4): int_17 = used_prompt_credits
    - Plan (field 6): int_12 = monthly_prompt_credits
    """
    result = {
        "user_used_prompt_credits": None,
        "team_used_prompt_credits": None,
        "monthly_prompt_credits": None,
        "remaining_credits": None,
    }
    
    class ProtobufParser:
        def __init__(self, data):
            self.data = data
            self.pos = 0
        
        def read_varint(self):
            value = 0
            shift = 0
            while self.pos < len(self.data):
                b = self.data[self.pos]
                self.pos += 1
                value |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            return value
        
        def parse_message(self):
            fields = {}
            while self.pos < len(self.data):
                if self.pos >= len(self.data):
                    break
                # 使用 varint 读取 tag，支持字段号 > 15
                tag = self.read_varint()
                if tag == 0:
                    break
                field_num = tag >> 3
                wire_type = tag & 0x07
                
                if wire_type == 0:  # varint
                    value = self.read_varint()
                    fields[f"int_{field_num}"] = value
                elif wire_type == 2:  # length-delimited
                    length = self.read_varint()
                    if self.pos + length <= len(self.data):
                        sub_data = self.data[self.pos:self.pos + length]
                        self.pos += length
                        
                        # 先尝试解析为 UTF-8 字符串
                        is_string = False
                        try:
                            text = sub_data.decode('utf-8')
                            if text and all(c.isprintable() or c in '\n\r\t' for c in text):
                                fields[f"string_{field_num}"] = text
                                is_string = True
                        except:
                            pass
                        
                        # 如果不是字符串，尝试解析为嵌套消息
                        if not is_string:
                            try:
                                sub_parser = ProtobufParser(sub_data)
                                sub_fields = sub_parser.parse_message()
                                if sub_fields:
                                    fields[f"subMesssage_{field_num}"] = sub_fields
                            except:
                                pass
                    else:
                        break
                else:
                    break
            return fields
    
    try:
        parser = ProtobufParser(data)
        parsed = parser.parse_message()
        
        # 提取 User (field 1)
        user = parsed.get("subMesssage_1", {})
        user_used_raw = user.get("int_28")
        if user_used_raw is not None:
            result["user_used_prompt_credits"] = user_used_raw // 100  # 除以100
        
        # 提取 Team (field 4)
        team = parsed.get("subMesssage_4", {})
        team_used_raw = team.get("int_17")
        if team_used_raw is not None:
            result["team_used_prompt_credits"] = team_used_raw // 100  # 除以100
        # team.int_15 = flex_credit_quota (额外配额)
        flex_quota_raw = team.get("int_15", 0)
        result["flex_credit_quota"] = flex_quota_raw // 100 if flex_quota_raw else 0
        
        # 提取 Plan (field 6)
        plan = parsed.get("subMesssage_6", {})
        monthly_raw = plan.get("int_12")
        if monthly_raw is not None:
            result["monthly_prompt_credits"] = monthly_raw // 100  # 除以100
        
        # 总配额 = 月度配额（不加 flex 配额，用用户自己的配额）
        monthly_val = result["monthly_prompt_credits"] or 0
        total_quota = monthly_val
        result["total_quota"] = total_quota
        
        # 计算已用积分：优先用团队的，否则用用户的（参考 windsurf-account-manager-simple）
        used = result["team_used_prompt_credits"] if result.get("team_used_prompt_credits") is not None else (result.get("user_used_prompt_credits") or 0)
        result["used_credits"] = used
        
        # 剩余积分 = 总配额 - 已用积分
        result["remaining_credits"] = max(0, total_quota - used)
        
        
    except Exception as e:
        result["parse_error"] = str(e)
        print(f"❌ [GetCurrentUser] 解析错误: {e}")
    
    return result


async def get_team_members(token: str) -> dict:
    """
    获取团队成员列表（包含每个成员的已用积分）
    需要管理员权限
    
    Args:
        token: 管理员的 Firebase ID Token
    
    Returns:
        dict: {
            "success": bool,
            "members": [{"email": str, "firebase_id": str, "prompts_used": int, ...}]
        }
    """
    url = f"{WINDSURF_BASE_URL}/exa.seat_management_pb.SeatManagementService/GetUsers"
    
    body = encode_string_field(1, token)
    
    headers = {
        "accept": "*/*",
        "connect-protocol-version": "1",
        "content-type": "application/proto",
        "x-auth-token": token,
        "Referer": "https://windsurf.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=body, headers=headers)
            
        status_code = response.status_code
        print(f"[GetTeamMembers] Status: {status_code}, size: {len(response.content)} bytes")
        
        if status_code == 200:
            data = response.content
            result = parse_team_members(data)
            result["success"] = True
            result["status_code"] = status_code
            result["timestamp"] = datetime.utcnow().isoformat()
            return result
        else:
            return {
                "success": False,
                "status_code": status_code,
                "error": "获取团队成员失败",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


def parse_team_members(data: bytes) -> dict:
    """
    解析 GetUsers 响应
    提取成员列表和每个成员的已用积分
    
    结构：
    - subMesssage_1: User[] (用户数组)
    - subMesssage_4: UserCascadeDetails[] (使用详情，通过 firebase_id 关联)
      - string_1: firebase_id
      - int_2: prompts_used (已用积分)
    """
    result = {"members": []}
    
    class ProtobufParser:
        def __init__(self, data):
            self.data = data
            self.pos = 0
        
        def read_varint(self):
            value = 0
            shift = 0
            while self.pos < len(self.data):
                b = self.data[self.pos]
                self.pos += 1
                value |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            return value
        
        def parse_message(self):
            fields = {}
            arrays = {}  # 存储重复字段
            while self.pos < len(self.data):
                if self.pos >= len(self.data):
                    break
                tag = self.read_varint()
                if tag == 0:
                    break
                field_num = tag >> 3
                wire_type = tag & 0x07
                
                if wire_type == 0:  # varint
                    value = self.read_varint()
                    fields[f"int_{field_num}"] = value
                elif wire_type == 2:  # length-delimited
                    length = self.read_varint()
                    if self.pos + length <= len(self.data):
                        sub_data = self.data[self.pos:self.pos + length]
                        self.pos += length
                        
                        # 先尝试解析为 UTF-8 字符串
                        is_string = False
                        try:
                            text = sub_data.decode('utf-8')
                            # 检查是否是可打印字符串（不包含控制字符）
                            if text and all(c.isprintable() or c in '\n\r\t' for c in text):
                                fields[f"string_{field_num}"] = text
                                is_string = True
                        except:
                            pass
                        
                        # 如果不是字符串，尝试解析为嵌套消息
                        if not is_string:
                            try:
                                sub_parser = ProtobufParser(sub_data)
                                sub_fields = sub_parser.parse_message()
                                if sub_fields:
                                    key = f"subMesssage_{field_num}"
                                    if key in arrays:
                                        arrays[key].append(sub_fields)
                                    elif key in fields:
                                        arrays[key] = [fields[key], sub_fields]
                                        del fields[key]
                                    else:
                                        fields[key] = sub_fields
                            except:
                                pass
                    else:
                        break
                else:
                    break
            # 合并数组
            fields.update(arrays)
            return fields
    
    try:
        parser = ProtobufParser(data)
        parsed = parser.parse_message()
        
        # 提取 UserCascadeDetails (field 4) - 成员使用详情
        cascade_details = parsed.get("subMesssage_4", [])
        if not isinstance(cascade_details, list):
            cascade_details = [cascade_details] if cascade_details else []
        
        # 构建 firebase_id -> prompts_used 映射
        # 注意：UserCascadeDetails 结构可能有嵌套，需要处理多种情况
        usage_map = {}
        for detail in cascade_details:
            # 尝试直接获取
            firebase_id = detail.get("string_1", "")
            prompts_used = detail.get("int_2", 0)
            
            # 如果没有 string_1，尝试从嵌套结构获取
            if not firebase_id:
                # 检查是否有嵌套的 subMesssage_4
                inner = detail.get("subMesssage_4", {})
                if isinstance(inner, dict):
                    prompts_used = inner.get("int_2", 0)
                    # firebase_id 可能在其他位置，先跳过
            
            if firebase_id:
                usage_map[firebase_id] = prompts_used // 100  # 除以100
        
        # 提取 Users (field 1)
        users = parsed.get("subMesssage_1", [])
        if not isinstance(users, list):
            users = [users] if users else []
        
        members = []
        for user in users:
            email = user.get("string_3", "")
            firebase_id = user.get("string_6", "")
            name = user.get("string_2", "")
            api_key = user.get("string_1", "")
            
            # 从 usage_map 获取该成员的已用积分
            prompts_used = usage_map.get(firebase_id, 0)
            
            members.append({
                "email": email,
                "name": name,
                "firebase_id": firebase_id,
                "api_key": api_key,
                "prompts_used": prompts_used,
            })
        
        result["members"] = members
        result["usage_map"] = usage_map  # 便于按 firebase_id 查找
        
        
    except Exception as e:
        result["parse_error"] = str(e)
        print(f"❌ [GetTeamMembers] 解析错误: {e}")
    
    return result


async def get_member_used_credits(admin_token: str, member_email: str) -> Optional[int]:
    """
    获取指定成员的已用积分
    
    Args:
        admin_token: 管理员的 Firebase ID Token
        member_email: 成员邮箱
    
    Returns:
        int: 已用积分，如果获取失败返回 None
    """
    result = await get_team_members(admin_token)
    if not result.get("success"):
        return None
    
    members = result.get("members", [])
    for member in members:
        if member.get("email", "").lower() == member_email.lower():
            return member.get("prompts_used", 0)
    
    return None


async def get_plan_status(token: str) -> dict:
    """
    获取套餐状态（积分/配额信息）
    比 GetUser 更轻量，专门用于刷新积分状态
    
    Args:
        token: Firebase ID Token
    
    Returns:
        dict: {"success": bool, "prompts_used": int, "prompts_limit": int, ...}
    """
    url = f"{WINDSURF_BASE_URL}/exa.seat_management_pb.SeatManagementService/GetPlanStatus"
    
    body = encode_string_field(1, token)
    
    headers = {
        "accept": "*/*",
        "connect-protocol-version": "1",
        "content-type": "application/proto",
        "x-auth-token": token,
        "Referer": "https://windsurf.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=body, headers=headers)
            
        status_code = response.status_code
        print(f"[GetPlanStatus] Status: {status_code}, size: {len(response.content)} bytes")
        
        if status_code == 200:
            # 解析protobuf响应
            data = response.content
            result = parse_plan_status(data)
            result["success"] = True
            result["status_code"] = status_code
            result["timestamp"] = datetime.utcnow().isoformat()
            return result
        else:
            return {
                "success": False,
                "status_code": status_code,
                "error": "获取计划状态失败",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


def parse_plan_status(data: bytes) -> dict:
    """
    解析GetPlanStatus响应 - 完整的protobuf解析器
    结构：GetPlanStatusResponse { plan_status(1): PlanStatus }
    PlanStatus {
        plan_info(1): PlanInfo { monthly_prompt_credits(12) },
        used_prompt_credits(6): int,
        available_prompt_credits(8): int
    }
    """
    result = {
        "prompts_used": None,
        "prompts_limit": None,
        "available_prompt_credits": None,
        "raw_length": len(data),
    }
    
    class ProtobufParser:
        def __init__(self, data):
            self.data = data
            self.pos = 0
        
        def read_varint(self):
            value = 0
            shift = 0
            while self.pos < len(self.data):
                b = self.data[self.pos]
                self.pos += 1
                value |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            return value
        
        def parse_message(self):
            fields = {}
            while self.pos < len(self.data):
                if self.pos >= len(self.data):
                    break
                tag = self.data[self.pos]
                if tag == 0:
                    break
                field_num = tag >> 3
                wire_type = tag & 0x07
                self.pos += 1
                
                if wire_type == 0:  # varint
                    value = self.read_varint()
                    fields[f"int_{field_num}"] = value
                elif wire_type == 2:  # length-delimited
                    length = self.read_varint()
                    if self.pos + length <= len(self.data):
                        sub_data = self.data[self.pos:self.pos + length]
                        self.pos += length
                        
                        # 尝试解析为嵌套消息
                        try:
                            sub_parser = ProtobufParser(sub_data)
                            sub_fields = sub_parser.parse_message()
                            if sub_fields:
                                fields[f"subMesssage_{field_num}"] = sub_fields
                        except:
                            # 可能是字符串
                            try:
                                text = sub_data.decode('utf-8')
                                if text.isprintable():
                                    fields[f"string_{field_num}"] = text
                            except:
                                pass
                    else:
                        break
                else:
                    # 跳过其他类型
                    break
            return fields
    
    try:
        parser = ProtobufParser(data)
        parsed = parser.parse_message()
        result["parsed"] = parsed
        
        # 解析结果日志（调试用，已隐藏）
        # print(f"🔍 [PlanStatus] 解析结果: {parsed}")
        
        # 提取 PlanStatus (field 1)
        plan_status = parsed.get("subMesssage_1", {})
        
        # 先打印完整的解析结果用于调试
        print(f"🔍 [PlanStatus] 完整解析结果: {plan_status}")
        
        # 从 PlanStatus 提取积分信息（基于官方 windsurf-grpc proto 定义）
        # 注意：API返回的值需要除以100才是实际积分
        # PlanStatus 字段映射:
        #   field 4: available_flex_credits (可用弹性积分)
        #   field 5: used_flow_credits (已用流程积分)
        #   field 6: used_prompt_credits (已用提示积分)
        #   field 7: used_flex_credits (已用弹性积分)
        #   field 8: 某个积分字段（需要确认具体含义）
        #   field 9: available_flow_credits (可用流程积分)
        
        # field 6: used_prompt_credits (已用积分)
        used_raw = plan_status.get("int_6")
        if used_raw is not None:
            result["prompts_used"] = used_raw // 100
        
        # field 8: 暂存原始值
        field_8_raw = plan_status.get("int_8")
        
        # field 4: available_flex_credits (可用弹性积分)
        flex_raw = plan_status.get("int_4", 0)
        result["available_flex_credits"] = flex_raw // 100 if flex_raw else 0
            
        # 从 PlanInfo (field 1 of PlanStatus) 提取月度积分上限
        plan_info = plan_status.get("subMesssage_1", {})
        # field 12: monthly_prompt_credits
        monthly_raw = plan_info.get("int_12")
        if monthly_raw is not None:
            result["prompts_limit"] = monthly_raw // 100
        
        # 计算剩余积分 = 月度配额 - 已用积分（参考 windsurf-account-manager-simple 前端计算方式）
        if result.get("prompts_limit") is not None and result.get("prompts_used") is not None:
            result["available_prompt_credits"] = max(0, result["prompts_limit"] - result["prompts_used"])
        elif field_8_raw is not None:
            # 如果没有月度配额，使用 field_8 作为备选
            result["available_prompt_credits"] = field_8_raw // 100
            
        # 积分解析结果日志
        print(f"╔══════════════════════════════════════════════════════════╗")
        print(f"║  📊 积分解析结果 (原始值÷100)")
        print(f"╠══════════════════════════════════════════════════════════╣")
        print(f"║  int_6 (used_raw):     {used_raw} -> 已用积分={result.get('prompts_used')}")
        print(f"║  int_8 (field_8_raw):  {field_8_raw} -> (÷100={field_8_raw // 100 if field_8_raw else None})")
        print(f"║  int_4 (flex_raw):     {flex_raw} -> 可用弹性积分={result.get('available_flex_credits')}")
        print(f"║  int_12 (monthly_raw): {monthly_raw} -> 月度配额={result.get('prompts_limit')}")
        print(f"╠══════════════════════════════════════════════════════════╣")
        print(f"║  计算: {result.get('prompts_limit')} - {result.get('prompts_used')} = {result.get('available_prompt_credits')} (剩余积分)")
        print(f"╚══════════════════════════════════════════════════════════╝")
        
    except Exception as e:
        result["parse_error"] = str(e)
        print(f"❌ [PlanStatus] 解析错误: {e}")
    
    return result


async def get_user_info(token: str) -> dict:
    """
    获取用户信息（包含积分等）
    
    Args:
        token: Firebase ID Token
    
    Returns:
        dict: 用户信息
    """
    url = f"{WINDSURF_BASE_URL}/exa.api_server_pb.ApiServerService/GetUser"
    
    body = encode_string_field(1, token)
    
    headers = {
        "accept": "*/*",
        "connect-protocol-version": "1",
        "content-type": "application/proto",
        "x-auth-token": token,
        "Referer": "https://windsurf.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=body, headers=headers)
            
        if response.status_code == 200:
            # 解析响应获取积分信息
            data = response.content
            result = parse_user_info(data)
            result["success"] = True
            result["timestamp"] = datetime.utcnow().isoformat()
            return result
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": "获取用户信息失败",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


def parse_user_info(data: bytes) -> dict:
    """
    解析GetUser响应，提取积分信息
    简化解析，主要提取prompts_used字段
    """
    result = {
        "prompts_used": None,
        "raw_length": len(data),
    }
    
    try:
        # 简单搜索prompts_used字段（field 8）
        # 这是一个简化的解析，实际protobuf解析更复杂
        i = 0
        while i < len(data):
            if i + 1 < len(data):
                # 检查field tag
                tag = data[i]
                field_num = tag >> 3
                wire_type = tag & 0x07
                
                if wire_type == 0:  # varint
                    i += 1
                    value = 0
                    shift = 0
                    while i < len(data):
                        b = data[i]
                        value |= (b & 0x7F) << shift
                        i += 1
                        if not (b & 0x80):
                            break
                        shift += 7
                    
                    # prompts_used 通常在特定位置
                    if 200 <= value <= 10000:  # 合理的积分范围
                        if result["prompts_used"] is None:
                            result["prompts_used"] = value
                elif wire_type == 2:  # length-delimited
                    i += 1
                    length = 0
                    shift = 0
                    while i < len(data):
                        b = data[i]
                        length |= (b & 0x7F) << shift
                        i += 1
                        if not (b & 0x80):
                            break
                        shift += 7
                    i += length
                else:
                    i += 1
            else:
                i += 1
    except Exception as e:
        result["parse_error"] = str(e)
    
    return result


async def login_with_email(email: str, password: str, db: "Session" = None) -> dict:
    """
    使用邮箱密码登录获取Firebase Token
    
    注意：这需要通过Firebase Auth API实现
    """
    import os
    
    # 优先级：环境变量 > 数据库配置 > 后备Key
    firebase_api_key = os.getenv("FIREBASE_API_KEY")
    
    # 尝试从数据库读取
    if not firebase_api_key and db:
        from app.models import Config
        config = db.query(Config).filter(Config.key == "firebase_api_key").first()
        if config:
            firebase_api_key = config.value
    
    # 后备Key
    if not firebase_api_key:
        firebase_api_key = "AIzaSyDsOl-1XpT5err0Tcnx8FFod1H8gVGIycY"
        print(f"⚠️ [FirebaseAuth] 使用后备API Key")
    
    print(f"🔐 [FirebaseAuth] 正在登录: {email}")
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            
        if response.status_code == 200:
            data = response.json()
            print(f"✅ [FirebaseAuth] 登录成功: {email}")
            return {
                "success": True,
                "id_token": data.get("idToken"),
                "refresh_token": data.get("refreshToken"),
                "expires_in": data.get("expiresIn"),
                "email": data.get("email"),
                "local_id": data.get("localId"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error", {}).get("message", "登录失败")
            print(f"❌ [FirebaseAuth] 登录失败: {email}, 错误: {error_msg}, HTTP状态: {response.status_code}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def refresh_token(refresh_token: str) -> dict:
    """
    刷新Firebase Token
    """
    firebase_api_key = "AIzaSyDnOKEz3WrBG8ScNfCkYHFPu3Bz5-LIC6c"
    
    url = f"https://securetoken.googleapis.com/v1/token?key={firebase_api_key}"
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=payload)
            
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "id_token": data.get("id_token"),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": "刷新Token失败",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
