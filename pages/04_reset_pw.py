import sqlite3
import os

# データベースへのパス（01_details.pyと同じ場所ならこれでOK）
db_path = "database.db" 

def reset_admin():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # adminのパスワードを「admin1234」に強制リセット
    new_pw = "admin789"
    cur.execute("UPDATE TB_ID SET password = ? WHERE user_id = 'admin'", (new_pw,))
    
    conn.commit()
    conn.close()
    print(f"✅ adminのパスワードを {new_pw} にリセットしました。")

if __name__ == "__main__":
    reset_admin()