import streamlit as st
import pandas as pd
import re
import time
from supabase import create_client

# --- 権限チェック：管理者以外は追い返す ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("login.py")
    st.stop()

if st.session_state.get('user_id') != 'admin':
    st.error("システム管理権限がありません。")
    st.switch_page("pages/01_details.py")
    st.stop()

# --- 1. 環境設定 (Supabaseへの接続) ---
def get_db_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# 2. ページ設定
st.set_page_config(layout="wide", page_title="システム管理")

st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] {display: none;}
        [data-testid="stSidebar"] {visibility: visible !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

if 'admin_page' not in st.session_state:
    st.session_state.admin_page = "👤 ユーザー管理"

with st.sidebar:
    st.title("⚙️ システム管理")
    if st.button("👤 ユーザー管理", use_container_width=True):
        st.session_state.admin_page = "👤 ユーザー管理"
    if st.button("🏢 部署管理", use_container_width=True):
        st.session_state.admin_page = "🏢 部署管理"
    if st.button("📝 案件修正", use_container_width=True):
        st.session_state.admin_page = "📝 案件修正"
    st.divider()
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.switch_page("login.py")

st.title(f"⚙️ {st.session_state.admin_page}")

# ==========================================
# 1. ユーザー管理
# ==========================================
if st.session_state.admin_page == "👤 ユーザー管理":
    try:
        supabase = get_db_connection()

        # Supabaseからデータ取得
        res_id = supabase.table("TB_ID").select("*").execute()
        res_staff = supabase.table("TB_staff").select("*").execute()
        res_team = supabase.table("TB_team").select("*").execute()
        res_post = supabase.table("TB_post").select("*").execute()

        df_id = pd.DataFrame(res_id.data)
        df_staff = pd.DataFrame(res_staff.data)
        df_teams = pd.DataFrame(res_team.data)
        df_posts = pd.DataFrame(res_post.data)

        if not df_id.empty:
            df_all = df_id.merge(df_staff, on="staff_id", how="left")
            df_all = df_all.merge(df_teams, on="team_id", how="left")
            df_all = df_all.merge(df_posts, on="post_id", how="left")
            
            df_all = df_all.rename(columns={
                "user_id": "ログインID",
                "staff_name": "名前",
                "team_name": "所属部署",
                "post_name": "役職",
                "password": "パスワード"
            })
        else:
            df_all = pd.DataFrame(columns=["ログインID", "名前", "所属部署", "役職", "パスワード", "team_id", "post_id", "staff_id"])

        df_show = df_all[['ログインID', '名前', '所属部署', '役職']].copy()
        df_show['パスワード'] = '********'
        df_show['役職'] = df_show['役職'].fillna('設定なし')

        event = st.dataframe(
            df_show, 
            use_container_width=True, 
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun"
        )
        st.divider()
        
        selected_rows = event.selection.rows

        if selected_rows:
            row_idx = selected_rows[0]
            target_user_id = df_all.iloc[row_idx]["ログインID"]
            user_data = df_all[df_all["ログインID"] == target_user_id].iloc[0]
        else:
            st.warning("👆 上の表から編集したいユーザーをタップして選択してください。")
            st.stop()

        with st.form("edit_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("名前（スタッフ名）", value=user_data["名前"])
                new_pw = st.text_input("新しいパスワード", value=user_data["パスワード"], type="password")
            with col2:
                team_list = df_teams["team_name"].tolist()
                current_team = user_data["所属部署"] if pd.notna(user_data["所属部署"]) else team_list[0]
                new_team_name = st.selectbox("所属部署変更", options=team_list, index=team_list.index(current_team))
                
                post_list = df_posts["post_name"].tolist()
                current_post = user_data["役職"] if user_data["役職"] != "設定なし" else post_list[0]
                new_post_name = st.selectbox("役職変更", options=post_list, index=post_list.index(current_post))
            
            if st.form_submit_button("情報を更新する"):
                if not re.fullmatch(r'[a-zA-Z0-9]+', new_pw):
                    st.error("❌ パスワードは半角英数字のみです。")
                else:
                    new_team_id = int(df_teams[df_teams["team_name"] == new_team_name]["team_id"].values[0])
                    new_post_id = int(df_posts[df_posts["post_name"] == new_post_name]["post_id"].values[0])
                    target_staff_id = user_data["staff_id"]
                    
                    # ★修正：Supabaseへの確実な更新処理
                    supabase.table("TB_ID").update({
                        "password": str(new_pw).strip(), 
                        "team_id": new_team_id,
                        "post_id": new_post_id
                    }).eq("user_id", target_user_id).execute()
                    
                    supabase.table("TB_staff").update({
                        "staff_name": str(new_name).strip()
                    }).eq("staff_id", int(target_staff_id)).execute()
                    
                    st.success(f"✅ {new_name} さんの情報を更新しました！")
                    time.sleep(1.0)
                    st.rerun()
    
    except Exception as e:
        st.error(f"システムエラーが発生しました: {e}")

# ==========================================
# 2. 部署管理
# ==========================================
elif st.session_state.admin_page == "🏢 部署管理":
    try:
        supabase = get_db_connection()
        res_dept = supabase.table("TB_team").select("*").execute()
        df_dept_view = pd.DataFrame(res_dept.data)
        
        st.subheader("部署マスター一覧")
        
        event_dept = st.dataframe(
            df_dept_view.rename(columns={'team_id':'ID', 'team_name':'部署名'}), 
            use_container_width=False,  
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            column_config={
                "ID": st.column_config.TextColumn("ID", width=60),
                "部署名": st.column_config.TextColumn("部署名", width=300)
            }
        )
        
        st.divider()
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.write("🔄 **部署名の名称変更**")
            selected_dept_rows = event_dept.selection.rows
            
            if selected_dept_rows:
                row_idx = selected_dept_rows[0]
                target_t_id = df_dept_view.iloc[row_idx]["team_id"]
                t_name_val = df_dept_view.iloc[row_idx]["team_name"]
                
                with st.form("dept_edit"):
                    st.write(f"対象ID: **{target_t_id}**")
                    new_t_name = st.text_input("新しい名称", value=t_name_val)
                    
                    if st.form_submit_button("名称変更を実行"):
                        t_id_int = int(target_t_id)
                        supabase.table("TB_team").update({"team_name": new_t_name}).eq("team_id", t_id_int).execute()
                        st.success(f"✅ 「{new_t_name}」に更新しました。")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.info("👆 上の表から修正したい部署を選択してください。")
        
        with col_d2:
            st.write("🆕 **新規部署の追加**")
            with st.form("dept_add"):
                add_id = st.text_input("新規部署ID")
                add_name = st.text_input("新規部署名")
                if st.form_submit_button("追加"):
                    existing_ids = df_dept_view["team_id"].astype(str).values
                    existing_names = df_dept_view["team_name"].values
                    
                    if str(add_id) in existing_ids:
                        st.error(f"❌ エラー：ID {add_id} は既に存在します。")
                    elif add_name in existing_names:
                        st.error(f"❌ エラー：部署名「{add_name}」は既に存在します。")
                    elif not add_id:
                        st.warning("⚠️ IDを入力してください")
                    elif not add_name:
                        st.warning("⚠️ 部署名を入力してください")
                    else:
                        supabase.table("TB_team").insert({"team_id": int(add_id), "team_name": add_name}).execute()
                        st.success(f"✅ 部署 {add_name} を追加しました！")
                        time.sleep(1.0)
                        st.rerun()
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")

# ==========================================
# 3. 案件修正
# ==========================================
elif st.session_state.admin_page == "📝 案件修正":
    st.subheader("🛠 案件ステータス強制リセット")
    target_id_input = st.text_input("修正する案件IDを入力してください", placeholder="例: 2026-D1-001")

    if target_id_input:
        clean_id = target_id_input.strip()
        try:
            supabase = get_db_connection()
            res_matter = supabase.table("TB_matter").select("matter_title, status_id, remarks").eq("matter_id", clean_id).execute()

            if res_matter.data:
                target_data = res_matter.data[0]
                m_title = target_data.get('matter_title', '無題')
                s_id = int(target_data.get('status_id', 1))
                current_remarks = target_data.get('remarks', '') or ""
                
                status_map = {1:"起案中", 2:"差し戻し", 3:"部署承認中", 4:"本部回議中", 5:"最終承認済", 6:"完了"}
                current_status_text = status_map.get(s_id, f"不明(ID:{s_id})")

                st.info(f"✅ **対象案件を確認しました**\n\n**案件ID:** {clean_id}\n**案件名:** {m_title}  \n**現在のステータス:** `{current_status_text}`")

                with st.form("admin_matter_fix"):
                    st.write("🔧 **ステータスの変更設定**")
                    new_status = st.selectbox(
                        "変更後のステータスを選択", 
                        options=[2, 3, 4, 5, 6], 
                        format_func=lambda x: status_map.get(x, "不明")
                    )

                    reason_options = [
                        "操作ミスによる救済（差し戻し依頼）",
                        "承認ルートの誤設定に伴うリセット",
                        "退職・異動に伴う権限代行修正",
                        "システム不具合による整合性確保"
                    ]
                    selected_reason = st.selectbox("修正理由を選択（固定）", options=reason_options)

                    if st.form_submit_button("🚨 ステータスを強制変更する"):
                        admin_id = st.session_state.get('user_id', 'UnknownAdmin')
                        fixed_remark = f"管理者({admin_id})による修正：{selected_reason}"
                        new_remarks = f"【{fixed_remark}】\n{current_remarks}"
                        
                        supabase.table("TB_matter").update({
                            "status_id": new_status,
                            "remarks": new_remarks
                        }).eq("matter_id", clean_id).execute()
                        
                        st.success(f"✅ 案件 {clean_id} の証跡を刻み、更新を完了しました。")
                        time.sleep(1.0)
                        st.rerun()
            else:
                st.error(f"❌ 案件ID「{clean_id}」は見つかりませんでした。")
                
        except Exception as e:
            st.error(f"データベース処理中にエラーが発生しました: {e}")
    else:
        st.caption("案件IDを入力してEnterを押すと、詳細が表示されます。")