import streamlit as st
import sqlite3
import pandas as pd
import re
import time
import os


# --- 権限チェック：管理者(post_id=1)以外は追い返す ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("login.py")
    st.stop()

# B. 一般ユーザー（post_idが1以外）が紛れ込んだら追い返す
if st.session_state.get('user_id') != 'admin':
    st.error("システム管理権限がありません。")
    st.switch_page("pages/01_details.py")
    st.stop()
# ----------------------------------------------

current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "../database.db")

# 1. ページ設定
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
        # --- パスの自動解決コードを追加 ---
        import os
        # 03_admin.pyから見て「一つ上の階層にあるdatabase.db」を絶対パスで取得
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "../database.db")
        
        # 修正：固定のパスではなく、計算した db_path を使う
        conn = sqlite3.connect(db_path, check_same_thread=False)
        # ------------------------------

        # 1. 必要なデータを一度に取得
        df_all = pd.read_sql('''
            SELECT 
                I.user_id AS ログインID, 
                S.staff_name AS 名前, 
                T.team_name AS 所属部署, 
                IFNULL(P.post_name, '設定なし') AS 役職,
                I.password AS パスワード,
                I.team_id,
                I.post_id
            FROM TB_ID I
            LEFT JOIN TB_staff S ON I.staff_id = S.staff_id
            LEFT JOIN TB_team T ON I.team_id = T.team_id
            LEFT JOIN TB_post P ON I.post_id = P.post_id
        ''', conn)
        df_teams = pd.read_sql('SELECT * FROM TB_team', conn)
        df_posts = pd.read_sql('SELECT * FROM TB_post', conn)
        conn.close()

        # 一覧表の表示
        df_show = df_all[['ログインID', '名前', '所属部署', '役職']].copy()
        df_show['パスワード'] = '********'
        df_show['役職'] = df_show['役職'].fillna('設定なし')

        # event変数に代入し、選択可能(selection_mode="single-row")にします
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
        
        # --- 【追加】表示データのクレンジング ---
        # 画面上で None と表示されるのを防ぐ
        display_post = user_data["役職"] if pd.notna(user_data["役職"]) else "設定なし"

        # 編集フォーム
        with st.form("edit_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                # 【追加箇所】名前の書き換え
                new_name = st.text_input("名前（スタッフ名）", value=user_data["名前"])
                # パスワード
                new_pw = st.text_input("新しいパスワード", value=user_data["パスワード"], type="password")
            with col2:
                # 部署選択
                team_list = df_teams["team_name"].tolist()
                current_team = user_data["所属部署"]
                new_team_name = st.selectbox("所属部署変更", options=team_list, index=team_list.index(current_team))
                # 役職選択
                post_list = df_posts["post_name"].tolist()
                # None対策：現在の役職がNoneなら「担当」をデフォルトにする等の処理
                current_post = user_data["役職"] if user_data["役職"] != "設定なし" else post_list[0]
                new_post_name = st.selectbox("役職変更", options=post_list, index=post_list.index(current_post))
            
            # 更新ボタン
            if st.form_submit_button("情報を更新する"):
                if not re.fullmatch(r'[a-zA-Z0-9]+', new_pw):
                    st.error("❌ パスワードは半角英数字のみです。")
                else:
                    new_team_id = int(df_teams[df_teams["team_name"] == new_team_name]["team_id"].values[0])
                    
                    # 修正：ここを db_path に変えるだけ！ (tryは追加しない)
                    conn_update = sqlite3.connect(db_path, check_same_thread=False)
                    cursor = conn_update.cursor()
                    
                    # ① パスワードと部署の更新
                    cursor.execute('UPDATE TB_ID SET password = ?, team_id = ? WHERE user_id = ?', 
                                   (new_pw, new_team_id, target_user_id))
                    
                    # ② スタッフ名の更新
                    cursor.execute('''
                        UPDATE TB_staff SET staff_name = ? 
                        WHERE staff_id = (SELECT staff_id FROM TB_ID WHERE user_id = ?)
                    ''', (new_name, target_user_id))
                    
                    conn_update.commit()
                    conn_update.close()
                    
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
        # ① 表示用
        conn = sqlite3.connect(db_path, check_same_thread=False) 
        df_dept_view = pd.read_sql('SELECT * FROM TB_team', conn)
        df_dept_view = pd.read_sql('SELECT * FROM TB_team', conn)
        conn.close()
        
        # 上段：部署一覧
        st.subheader("部署マスター一覧")
        
        event_dept = st.dataframe(
            df_dept_view.rename(columns={'team_id':'ID', 'team_name':'部署名'}), 
            use_container_width=False,  # ★ここをFalseに。これで右側の余白を消せます
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            column_config={
                "ID": st.column_config.TextColumn("ID", width=60),
                "部署名": st.column_config.TextColumn("部署名", width=300)
            }
        )
        
        st.divider()
        # 下段：2カラム（左に変更、右に追加）
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.write("🔄 **部署名の名称変更**")
            
            # 表の選択状態を取得
            selected_dept_rows = event_dept.selection.rows
            
            if selected_dept_rows:
                # 選択された行のデータを特定
                row_idx = selected_dept_rows[0]
                target_t_id = df_dept_view.iloc[row_idx]["team_id"]
                t_name_val = df_dept_view.iloc[row_idx]["team_name"]
                
                with st.form("dept_edit"):
                    st.write(f"対象ID: **{target_t_id}**")
                    new_t_name = st.text_input("新しい名称", value=t_name_val)
                    
                    if st.form_submit_button("名称変更を実行"):
                        # IDを整数型に変換（これが格納成功の鍵でした）
                        t_id_int = int(target_t_id)
                        
                        # 保存処理
                        with sqlite3.connect(db_path) as conn_edit:
                            cursor = conn_edit.cursor()
                            cursor.execute(
                                'UPDATE TB_team SET team_name = ? WHERE team_id = ?', 
                                (new_t_name, t_id_int)
                            )
                            conn_edit.commit()

                        # 画面への通知とリフレッシュ
                        st.success(f"✅ 「{new_t_name}」に更新しました。")
                        time.sleep(0.5)
                        st.rerun()
            else:
                # 【B. 何も選ばれていない場合】
                st.info("👆 上の表から修正したい部署を選択してください。")
                # ★ここにボタンや入力欄は置かない（空振りを防ぐため）
        
        with col_d2:
            st.write("🆕 **新規部署の追加**")
            with st.form("dept_add"):
                add_id = st.text_input("新規部署ID")
                add_name = st.text_input("新規部署名")
                if st.form_submit_button("追加"):
                    # 既存のIDと名前のリストを取得
                    existing_ids = df_dept_view["team_id"].astype(str).values
                    existing_names = df_dept_view["team_name"].values
                    
                    if str(add_id) in existing_ids:
                        st.error(f"❌ エラー：ID {add_id} は既に存在します。")
                    
                    # ★追加：名前の重複チェック
                    elif add_name in existing_names:
                        st.error(f"❌ エラー：部署名「{add_name}」は既に存在します。")
                    
                    elif not add_id:
                        st.warning("⚠️ IDを入力してください")
                    elif not add_name:
                        st.warning("⚠️ 部署名を入力してください")
                    else:
                        # ここにINSERT処理...
                        conn_add = sqlite3.connect(db_path, check_same_thread=False)
                        cursor = conn_add.cursor()
                        cursor.execute('INSERT INTO TB_team (team_id, team_name) VALUES (?, ?)', (add_id, add_name))
                        conn_add.commit()
                        conn_add.close()
                        
                        st.success(f"✅ 部署 {add_name} を追加しました！")
                        import time
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
        # DBを検索
        with sqlite3.connect(db_path) as conn:
            query = "SELECT matter_title, status_id FROM TB_matter WHERE matter_id = ?"
            res = pd.read_sql(query, conn, params=(target_id_input,))

        if not res.empty:
            m_title = res.iloc[0]['matter_title']
            s_id = int(res.iloc[0]['status_id'])
            status_map = {1:"起案中", 2:"差し戻し", 3:"部署承認中", 4:"本部回議中", 5:"最終承認済", 6:"完了"}
            current_status_text = status_map.get(s_id, f"不明(ID:{s_id})")

            # 確認用表示
            st.info(f"✅ **対象案件を確認しました**\n\n**案件名:** {m_title}  \n**現在のステータス:** `{current_status_text}`")

            # 2. 修正用フォーム
            with st.form("admin_matter_fix"):
                st.write("🔧 **ステータスの変更設定**")
                new_status = st.selectbox(
                    "変更後のステータスを選択", 
                    options=[2, 3, 4, 5, 6], 
                    format_func=lambda x: status_map.get(x, "不明")
                )

                # 修正理由を固定。selectboxなので文字の改ざんや消去は不可能です。
                reason_options = [
                    "操作ミスによる救済（差し戻し依頼）",
                    "承認ルートの誤設定に伴うリセット",
                    "退職・異動に伴う権限代行修正",
                    "システム不具合による整合性確保"
                ]
                selected_reason = st.selectbox("修正理由を選択（固定）", options=reason_options)

                if st.form_submit_button("🚨 ステータスを強制変更する"):
                    # 実行者のIDを取得して、誰がいつ何をしたか証跡を確定させる
                    admin_id = st.session_state.get('user_id', 'UnknownAdmin')
                    fixed_remark = f"管理者({admin_id})による修正：{selected_reason}"
                    
                    with sqlite3.connect(db_path) as conn_update:
                        cur = conn_update.cursor()
                        # カラム名は定義書に基づき 'remarks' を使用
                        cur.execute("""
                            UPDATE TB_matter 
                            SET status_id = ?, 
                                remarks = '【' || ? || '】' || '\n' || COALESCE(remarks, '')
                            WHERE matter_id = ?
                        """, (new_status, fixed_remark, target_id_input))
                        conn_update.commit()
                    
                    st.success(f"✅ 案件 {target_id_input} の証跡を刻み、更新を完了しました。")
                    time.sleep(1.0)
                    st.rerun()
        else:
            st.error(f"❌ 案件ID「{target_id_input}」は見つかりませんでした。")
    else:
        st.caption("案件IDを入力してEnterを押すと、詳細が表示されます。")