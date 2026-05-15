import streamlit as st
import sqlite3

st.set_page_config(page_title="開発管理統合システム", 
layout="wide",
initial_sidebar_state="expanded" # 最初から開いておくが、中身は自分で書く
)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row 
    return conn

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
            # 1. ログイン処理だけをSupabaseに切り替える（上の設定はいじらなくてOKです）
            from supabase import create_client
            supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
            
            # 2. TB_IDから照合してデータを取得（staff_idも一緒に取ってくる）
            res_id = supabase.table("TB_ID").select("user_id, team_id, post_id, staff_id").eq("user_id", user_id).eq("password", password).execute()

            if res_id.data:
                user_data = res_id.data[0]
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user_data['user_id']
                st.session_state['team_id'] = user_data['team_id']
                st.session_state['post_id'] = user_data['post_id']
                st.session_state['role_id'] = user_data['post_id'] 
                
                # 3. 取ってきたstaff_idを使って、TB_staffから「最新の名前」を取る！
                res_staff = supabase.table("TB_staff").select("staff_name").eq("staff_id", user_data['staff_id']).execute()
                
                if res_staff.data:
                    st.session_state['user_name'] = res_staff.data[0]['staff_name']
                else:
                    st.session_state['user_name'] = user_data['user_id']
                
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
