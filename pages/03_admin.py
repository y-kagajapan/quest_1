import streamlit as st
import pandas as pd
import re
import time
from supabase import create_client # ★sqlite3やosを削除し、Supabaseを追加

# --- 権限チェック：管理者以外は追い返す ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("login.py")
    st.stop()

# B. 一般ユーザーが紛れ込んだら追い返す
if st.session_state.get('user_id') != 'admin':
    st.error("システム管理権限がありません。")
    st.switch_page("pages/01_details.py")
    st.stop()
# ----------------------------------------------

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
        /* 標準のページナビゲーション（login, details等）を非表示 */
        [data-testid="stSidebarNav"] {display: none;}
        
        /* サイドバーそのものは表示する（自作ボタンを出すため） */
        [data-testid="stSidebar"] {visibility: visible !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- サイドバー：メニュー切り替え（ボタン形式） ---
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
        # 1. セッション情報をすべて消去（ログイン状態を解除）
        st.session_state.clear()
        
        # 2. ログイン画面（メインファイル）へ切り替え
        st.switch_page("login.py")

# --- メインエリア ---
st.title(f"⚙️ {st.session_state.admin_page}")

# ==========================================
# 1. ユーザー管理
# ==========================================
if st.session_state.admin_page == "👤 ユーザー管理":
    try:
        supabase = get_db_connection()

        # 1. 必要なデータをSupabaseから取得してPandasで結合
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
            
            # 列名の整形
            df_all = df_all.rename(columns={
                "user_id": "ログインID",
                "staff_name": "名前",
                "team_name": "所属部署",
                "post_name": "役職",
                "password": "パスワード"
            })
        else:
            df_all = pd.DataFrame(columns=["ログインID", "名前", "所属部署", "役職", "パスワード", "team_id", "post_id", "staff_id"])

        # 一覧表の表示
        df_show = df_all[['ログインID', '名前', '所属部署', '役職']].copy()
        df_show['パスワード'] = '********'
        df_show['役職'] = df_show['役職'].fillna('設定なし')

        # event変数に代入し、選択可能にします
        event = st.dataframe(
            df_show, 
            use_container_width=True, 
            hide_index=True,
            selection_mode="single-row", # 1行選択
            on_select="rerun"            # 選択時に即反映
        )
        st.divider()
        
        # 編集対象の選択
        selected_rows = event.selection.rows

        if selected_rows:
            # 選択された行のデータを特定
            row_idx = selected_rows[0]
            target_user_id = df_all.iloc[row_idx]["ログインID"]
            user_data = df_all[df_all["ログインID"] == target_user_id].iloc[0]
        else:
            # 何も選ばれていない時はメッセージを出して止める
            st.warning("👆 上の表から編集したいユーザーをタップして選択してください。")
            st.stop()
        
        # 表示データのクレンジング
        display_post = user_data["役職"] if pd.notna(user_data["役職"]) else "設定なし"

        # 編集フォーム
        with st.form("edit_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("名前（スタッフ名）", value=user_data["名前"])
                new_pw = st.text_input("新しいパスワード", value=user_data["パスワード"], type="password")
            with col2:
                # 部署選択
                team_list = df_teams["team_name"].tolist()
                current_team = user_data["所属部署"]
                new_team_name = st.selectbox("所属部署変更", options=team_list, index=team_list.index(current_team))
                
                # 役職選択
                post_list = df_posts["post_name"].tolist()
                current_post = user_data["役職"] if user_data["役職"] != "設定なし" else post_list[0]
                new_post_name = st.selectbox("役職変更", options=post_list, index=post_list.index(current_post))
            
            # 更新ボタン
            if st.form_submit_button("情報を更新する"):
                if not re.fullmatch(r'[a-zA-Z0-9]+', new_pw):
                    st.error("❌ パスワードは半角英数字のみです。")
                else:
                    # 選ばれた部署と役職のIDを取得
                    new_team_id = int(df_teams[df_teams["team_name"] == new_team_name]["team_id"].values[0])
                    new_post_id = int(df_posts[df_posts["post_name"] == new_post_name]["post_id"].values[0])
                    target_staff_id = user_data["staff_id"]
                    
                    # Supabaseへの保存処理（更新）
                    # ① パスワード、部署、役職の更新 (TB_ID)
                    supabase.table("TB_ID").update({
                        "password": new_pw, 
                        "team_id": new_team_id,
                        "post_id": new_post_id # ★修正漏れを補強
                    }).eq("user_id", target_user_id).execute()
                    
                    # ② スタッフ名の更新 (TB_staff)
                    supabase.table("TB_staff").update({
                        "staff_name": new_name
                    }).eq("staff_id", target_staff_id).execute()
                    
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
        
        # ① 表示用データ取得
        res_dept = supabase.table("TB_team").select("*").execute()
        df_dept_view = pd.DataFrame(res_dept.data)
        
        # 上段：部署一覧
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
        # 下段：2カラム
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
                        
                        # 保存処理 (Supabase)
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
                        # 新規追加処理 (Supabase)
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

    # 1. 案件IDの入力
    target_id_input = st.text_input("修正する案件IDを入力してください", placeholder="例: 2026-D1-001")

    if target_id_input:
        try:
            supabase = get_db_connection()
            
            # 不正を防ぐため、余計な変換はせず「前後の空白削除」のみ行う（厳密な完全一致用）
            clean_id = target_id_input.strip()
            
            # ★修正: 細かい列指定によるエラーを防ぐため、他の画面と同じく `select("*")` で確実に全件取得する
            res_matter = supabase.table("TB_matter").select("*").execute()
            df_matter = pd.DataFrame(res_matter.data)
            
            if not df_matter.empty:
                # データベース側の見えない空白なども考慮して、純粋な文字同士で「完全一致」するか判定
                df_matter['matter_id_clean'] = df_matter['matter_id'].astype(str).str.strip()
                match_df = df_matter[df_matter['matter_id_clean'] == clean_id]

                if not match_df.empty:
                    target_data = match_df.iloc[0]
                    actual_db_id = target_data['matter_id'] # 更新用にDBの生のIDを保持
                    m_title = target_data['matter_title']
                    s_id = int(target_data['status_id']) if pd.notna(target_data['status_id']) else 1
                    current_remarks = target_data['remarks'] if pd.notna(target_data['remarks']) and target_data['remarks'] else ""
                    
                    status_map = {1:"起案中", 2:"差し戻し", 3:"部署承認中", 4:"本部回議中", 5:"最終承認済", 6:"完了"}
                    current_status_text = status_map.get(s_id, f"不明(ID:{s_id})")

                    # 確認用表示
                    st.info(f"✅ **対象案件を確認しました**\n\n**案件ID:** {clean_id}\n**案件名:** {m_title}  \n**現在のステータス:** `{current_status_text}`")

                    # 2. 修正用フォーム
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
                            
                            # 証跡コメントを先頭に追加
                            new_remarks = f"【{fixed_remark}】\n{current_remarks}"
                            
                            # 保存処理 (Supabase) - DBの生のIDを使って確実に更新
                            supabase.table("TB_matter").update({
                                "status_id": new_status,
                                "remarks": new_remarks
                            }).eq("matter_id", actual_db_id).execute()
                            
                            st.success(f"✅ 案件 {clean_id} の証跡を刻み、更新を完了しました。")
                            time.sleep(1.0)
                            st.rerun()
                else:
                    st.error(f"❌ 案件ID「{clean_id}」は見つかりませんでした。正確に入力されているか確認してください。")
            else:
                 st.error("データベースに案件が1件も登録されていません。")
                
        except Exception as e:
            st.error(f"データベース処理中にエラーが発生しました: {e}")
    else:
        st.caption("案件IDを入力してEnterを押すと、詳細が表示されます。")