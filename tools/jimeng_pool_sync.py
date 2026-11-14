"""
即梦账号池集成脚本
将 any-auto-register 注册的即梦账号同步到 jimeng-free-api-all 的账号池
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# 账号池数据库路径
DB_PATH = Path("/Users/admin/Desktop/myapps/jimeng-free-api-all/data/jimeng.db")


def create_account_in_pool(
    name: str,
    session_id: str,
    session_id_ss: str = "",
    enabled: bool = True,
) -> dict:
    """
    在 jimeng-free-api-all 账号池中创建账号

    Args:
        name: 账号名称
        session_id: 主 sessionid
        session_id_ss: 备用 sessionid_ss
        enabled: 是否启用

    Returns:
        创建的账号信息
    """
    if not DB_PATH.exists():
        return {"error": f"数据库不存在：{DB_PATH}"}

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # 检查是否已存在
        cursor.execute(
            "SELECT id FROM jimeng_accounts WHERE name = ?",
            (name,),
        )
        existing = cursor.fetchone()

        if existing:
            return {"error": f"账号已存在：{name}", "id": existing[0]}

        # 生成账号 ID
        import uuid
        account_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # 加密凭证（简化版，实际应使用 AES-256-GCM）
        credential_kind = "sessionid"
        credential_hash = hash(session_id) & 0xFFFFFFFF
        credential_ciphertext = session_id  # 实际应加密

        # 插入账号
        cursor.execute(
            """
            INSERT INTO jimeng_accounts (
                id, name, credential_kind, credential_hash,
                credential_ciphertext, enabled, failure_count,
                success_count, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
            """,
            (
                account_id,
                name,
                credential_kind,
                credential_hash,
                credential_ciphertext,
                1 if enabled else 0,
                json.dumps({"session_id_ss": session_id_ss}),
                now,
                now,
            ),
        )

        conn.commit()

        return {
            "success": True,
            "id": account_id,
            "name": name,
            "credential_kind": credential_kind,
            "enabled": enabled,
        }

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        conn.close()


def list_accounts() -> list:
    """列出账号池中的所有账号"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, name, credential_kind, enabled,
                   failure_count, success_count, created_at
            FROM jimeng_accounts
            ORDER BY created_at DESC
            """
        )

        accounts = []
        for row in cursor.fetchall():
            accounts.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "credential_kind": row[2],
                    "enabled": bool(row[3]),
                    "failure_count": row[4],
                    "success_count": row[5],
                    "created_at": row[6],
                }
            )

        return accounts
    finally:
        conn.close()


def delete_account(account_id: str) -> dict:
    """删除账号"""
    if not DB_PATH.exists():
        return {"error": "数据库不存在"}

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM jimeng_accounts WHERE id = ?",
            (account_id,),
        )
        conn.commit()

        if cursor.rowcount > 0:
            return {"success": True, "deleted": account_id}
        else:
            return {"error": f"账号不存在：{account_id}"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        conn.close()


# 测试代码
if __name__ == "__main__":
    print("即梦账号池集成工具")
    print("=" * 50)

    # 列出所有账号
    print("\n当前账号池：")
    accounts = list_accounts()
    if accounts:
        for acc in accounts:
            status = "✅" if acc["enabled"] else "❌"
            print(f"  {status} {acc['name']} ({acc['credential_kind']})")
            print(f"     成功：{acc['success_count']}  失败：{acc['failure_count']}")
    else:
        print("  (空)")

    # 示例：创建测试账号
    print("\n创建测试账号...")
    result = create_account_in_pool(
        name="test@example.com",
        session_id="test_session_id_12345",
        session_id_ss="test_session_id_ss_67890",
        enabled=True,
    )
    print(f"结果：{result}")
