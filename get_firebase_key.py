#!/usr/bin/env python3
"""
自动获取 Windsurf/Codeium 的 Firebase API Key

使用方法:
    python get_firebase_key.py
"""

import re
import sys
import httpx
import asyncio


async def get_firebase_key():
    """从 Windsurf/Codeium 网站获取 Firebase API Key"""
    
    urls = [
        'https://windsurf.com',
        'https://www.windsurf.com',
        'https://codeium.com',
        'https://www.codeium.com',
        'https://codeium.com/profile',
        'https://www.codeium.com/profile'
    ]
    
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for url in urls:
            try:
                print(f"正在检查: {url}")
                response = await client.get(
                    url,
                    headers={'User-Agent': user_agent}
                )
                html = response.text
                
                # 搜索 Firebase API Key
                match = re.search(r'AIza[0-9A-Za-z_-]{35}', html)
                if match:
                    api_key = match.group(0)
                    print(f"\n✅ 找到 Firebase API Key: {api_key}")
                    return api_key
                
                # 提取并扫描 JS 文件
                script_urls = re.findall(r'src=["\'](([^"\']+\.js))["\'"]', html)
                
                for script_match in script_urls[:5]:  # 只扫描前5个
                    js_url = script_match[0]
                    if js_url.startswith('/'):
                        js_url = url.rstrip('/') + js_url
                    elif not js_url.startswith('http'):
                        js_url = url.rstrip('/') + '/' + js_url
                    
                    # 只扫描主要文件
                    if any(keyword in js_url for keyword in ['main', 'app', 'index', 'chunk']):
                        try:
                            print(f"  扫描 JS: {js_url[:80]}...")
                            js_response = await client.get(
                                js_url,
                                headers={'User-Agent': user_agent},
                                timeout=5.0
                            )
                            js_content = js_response.text
                            
                            js_match = re.search(r'AIza[0-9A-Za-z_-]{35}', js_content)
                            if js_match:
                                api_key = js_match.group(0)
                                print(f"\n✅ 找到 Firebase API Key: {api_key}")
                                return api_key
                        except Exception as e:
                            print(f"  跳过: {str(e)[:50]}")
                            continue
                            
            except Exception as e:
                print(f"❌ 失败 ({url}): {str(e)[:50]}")
                continue
    
    return None


async def main():
    """主函数"""
    print("=" * 60)
    print("Firebase API Key 自动获取工具")
    print("=" * 60)
    print()
    
    api_key = await get_firebase_key()
    
    print()
    print("=" * 60)
    
    if api_key:
        print("✅ 成功获取 Firebase API Key!")
        print()
        print("请将以下内容添加到 .env 文件中：")
        print("-" * 60)
        print(f"FIREBASE_API_KEY={api_key}")
        print("-" * 60)
        print()
        print("然后重启服务：")
        print("  docker-compose down")
        print("  docker-compose up -d")
        print()
        return 0
    else:
        print("❌ 未能自动获取 Firebase API Key")
        print()
        print("请手动获取：")
        print("1. 访问 https://windsurf.com")
        print("2. 按 F12 打开开发者工具")
        print("3. 切换到 Network 标签")
        print("4. 刷新页面")
        print("5. 搜索 'firebase' 或 'identitytoolkit'")
        print("6. 在请求 URL 中找到 key= 参数")
        print()
        print("详细说明请查看: GET_FIREBASE_KEY.md")
        print()
        return 1


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n错误: {e}")
        sys.exit(1)
