"""
测试账号密码登录功能
"""
import asyncio
import sys
from app.windsurf_login import windsurf_login


async def test_login():
    """测试登录功能"""
    print("=" * 60)
    print("Windsurf 账号密码登录测试")
    print("=" * 60)
    
    # 从命令行参数获取邮箱和密码
    if len(sys.argv) < 3:
        print("\n使用方法:")
        print("  python test_login.py <email> <password>")
        print("\n示例:")
        print("  python test_login.py test@example.com mypassword")
        return
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    print(f"\n邮箱: {email}")
    print(f"密码: {'*' * len(password)}")
    print("\n开始登录...\n")
    
    try:
        result = await windsurf_login(email, password)
        
        print("=" * 60)
        print("✅ 登录成功！")
        print("=" * 60)
        print(f"\n邮箱: {result['email']}")
        print(f"用户名: {result['name']}")
        print(f"API Key: {result['api_key']}")
        print("\n" + "=" * 60)
        
    except Exception as e:
        print("=" * 60)
        print("❌ 登录失败")
        print("=" * 60)
        print(f"\n错误信息: {str(e)}")
        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_login())
