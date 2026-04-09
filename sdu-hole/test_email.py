"""
山大邮箱 SMTP 连接测试脚本
用法: python test_email.py

运行前请先修改下面三个变量！
"""

import smtplib
from email.mime.text import MIMEText

# ============================================================
# 👇👇👇 请修改这三行 👇👇👇
# ============================================================
MY_STUDENT_ID = "你的学号"                    # 例如 202312345
MY_EMAIL_PASSWORD = "你的邮箱密码"             # 登录 mail.sdu.edu.cn 的密码
SEND_TO = "你的学号"                          # 测试发给自己，填同一个学号即可
# ============================================================

SMTP_HOST = "smtp.sdu.edu.cn"
SMTP_PORT = 25
FROM_EMAIL = f"{MY_STUDENT_ID}@mail.sdu.edu.cn"
TO_EMAIL = f"{SEND_TO}@mail.sdu.edu.cn"


def test():
    print(f"\n{'='*50}")
    print(f"  山大邮箱 SMTP 连接测试")
    print(f"  服务器: {SMTP_HOST}:{SMTP_PORT}")
    print(f"  发件人: {FROM_EMAIL}")
    print(f"  收件人: {TO_EMAIL}")
    print(f"{'='*50}\n")

    # Step 1: 连接
    print("① 连接 SMTP 服务器...")
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        print(f"   ✅ 连接成功！")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        print(f"\n   可能原因:")
        print(f"   - 不在校园网内（smtp.sdu.edu.cn 可能仅限校内访问）")
        print(f"   - 防火墙拦截了 25 端口")
        return

    # Step 2: 登录
    print("② 登录认证...")
    try:
        server.login(FROM_EMAIL, MY_EMAIL_PASSWORD)
        print(f"   ✅ 登录成功！")
    except smtplib.SMTPAuthenticationError as e:
        print(f"   ❌ 登录失败（用户名或密码错误）: {e}")
        print(f"\n   请确认:")
        print(f"   - 学号是否正确: {MY_STUDENT_ID}")
        print(f"   - 密码是否是登录 mail.sdu.edu.cn 的密码")
        print(f"   - 初始密码为身份证号（字母大写）")
        server.quit()
        return
    except Exception as e:
        print(f"   ❌ 登录异常: {e}")
        server.quit()
        return

    # Step 3: 发送测试邮件
    print("③ 发送测试邮件...")
    try:
        html = """
        <div style="max-width:400px;margin:0 auto;padding:24px;font-family:sans-serif;">
            <h2>🕳️ 山大树洞</h2>
            <p>恭喜！SMTP 连接测试成功！</p>
            <div style="font-size:36px;font-weight:bold;letter-spacing:10px;
                        color:#c2410c;padding:24px;background:#fef3e8;
                        border-radius:12px;text-align:center;margin:20px 0;">
                888888
            </div>
            <p style="color:#999;font-size:12px;">
                这是一封测试邮件，说明你的山大树洞已经可以发送验证码了！
            </p>
        </div>
        """
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = "【山大树洞】SMTP 测试成功！"
        msg["From"] = f"山大树洞 <{FROM_EMAIL}>"
        msg["To"] = TO_EMAIL

        server.sendmail(FROM_EMAIL, [TO_EMAIL], msg.as_string())
        print(f"   ✅ 邮件发送成功！")
        print(f"\n🎉 测试全部通过！请去 mail.sdu.edu.cn 查收测试邮件。")
        print(f"\n接下来修改 .env 文件:")
        print(f"   EMAIL_MODE=smtp")
        print(f"   SMTP_HOST=smtp.sdu.edu.cn")
        print(f"   SMTP_PORT=25")
        print(f"   SMTP_USER={FROM_EMAIL}")
        print(f"   SMTP_PASSWORD=你的邮箱密码")
        print(f"   SMTP_USE_STARTTLS=false")
        print(f"\n然后重启后端: uvicorn app.main:app --reload --port 8000")

    except Exception as e:
        print(f"   ❌ 发送失败: {e}")
    finally:
        server.quit()


if __name__ == "__main__":
    if "你的学号" in MY_STUDENT_ID:
        print("\n⚠️  请先打开 test_email.py，修改文件顶部的学号和密码！\n")
    else:
        test()
