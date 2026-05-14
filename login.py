import streamlit as st
import sqlite3
from supabase import create_client

st.set_page_config(page_title="開発管理統合システム", 
layout="wide",
initial_sidebar_state="expanded" # 最初から開いておくが、中身は自分で書く
)

def get_db_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# 2. 強力な目隠し（サイドバーを中身ごと消す設定）
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.markdown(
        """
        <style>
            /* サイドバーのナビゲーションを非表示 */
            [data-testid="stSidebarNav"] {display: none;}
            /* サイドバーそのものを閉じる（もし開いていても） */
            [data-testid="stSidebar"] {visibility: hidden;}
            /* メインコンテンツを左に詰めず、中央に保つ */
            .main .block-container {max-width: 800px; padding-top: 10rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

# 3. ログインロジック
st.title("🛡️ 開発管理統合システム　ログイン画面")

# 中央寄せのレイアウト
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.write("---")
    
    # 💡 Formで囲むことで、Enterキーが効くようになります
    with st.form("login_form", clear_on_submit=False):
        user_id = st.text_input("ユーザーID", placeholder="IDを入力してください")
        password = st.text_input("パスワード", type="password", placeholder="パスワードを入力してください")
        
        # 💡 st.button ではなく form_submit_button を使います
        submit_button = st.form_submit_button("ログイン", use_container_width=True)
        
        if submit_button:
            supabase = get_db_connection()
            
            # SupabaseのテーブルからIDとパスワードを照合
            response = supabase.table("TB_ID").select("user_id, team_id, post_id").eq("user_id", user_id).eq("password", password).execute()
            
            # データが見つかったか判定（リストが空でなければ成功）
            user_data_list = response.data
            user_data = user_data_list[0] if user_data_list else None

            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user_data[0]   # 例: 'D1S01' など
                st.session_state['team_id'] = user_data[1]
                st.session_state['post_id'] = user_data[2]   # 役職ID
                st.session_state['role_id'] = user_data[2] 
                st.session_state['user_name'] = user_data[0]
                
                if st.session_state['user_id'] == 'admin':
                    st.success("管理者としてログインしました")
                    st.switch_page("pages/03_admin.py") 
                else:
                    st.success(f"{st.session_state['user_id']} としてログインしました")
                    st.switch_page("pages/01_details.py")
            else:
                st.error("IDまたはパスワードが正しくありません")

# ログイン済みの場合のメッセージ
if st.session_state.get('logged_in'):
    st.info("ログイン済みです。左のサイドバーからメニューを選択してください。")
    # ログイン後はサイドバーを自動で開く設定なども可能
