import random

import chess
import chess.svg
import streamlit as st

import common

common.setup_page("チェス", "♟️")
common.hero("♟️ デジタルチェス", "駒と行き先を えらんで ゲームしよう！ 白があなたです。")

PIECE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0,
}
PIECE_NAMES = {
    chess.PAWN: "ポーン", chess.KNIGHT: "ナイト", chess.BISHOP: "ビショップ",
    chess.ROOK: "ルーク", chess.QUEEN: "クイーン", chess.KING: "キング",
}
DIFFICULTY_DEPTH = {"Hard": 2, "Very Hard": 3}

DEFAULTS = {"chess_board": chess.Board()}
common.init_state(DEFAULTS)

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定（せってい）")
    mode = st.radio("あそびかた", ("1人プレイ（CPU戦）", "2人プレイ"))
    difficulty = None
    if mode == "1人プレイ（CPU戦）":
        difficulty = st.selectbox("むずかしさ（難易度）", ("Easy", "Normal", "Hard", "Very Hard"), index=1)
        st.caption("Easy：ランダム ／ Normal：駒をとりたがる ／ Hard・Very Hard：先を読んで考える")
    st.write("---")
    undo_col, reset_col = st.columns(2)
    if undo_col.button("↩️ 1手もどす", use_container_width=True):
        board = st.session_state.chess_board
        steps = 2 if mode.startswith("1人") else 1
        for _ in range(steps):
            if board.move_stack:
                board.pop()
        st.rerun()
    if reset_col.button("🔄 リセット", type="primary", use_container_width=True):
        st.session_state.chess_board = chess.Board()
        st.rerun()

board = st.session_state.chess_board


# --- CPUの思考 ---
def evaluate(b):
    """白から見た駒の価値の差。"""
    if b.is_checkmate():
        return -100000 if b.turn == chess.WHITE else 100000
    if b.is_stalemate() or b.is_insufficient_material():
        return 0
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += value * (len(b.pieces(piece_type, chess.WHITE)) - len(b.pieces(piece_type, chess.BLACK)))
    return score


def ordered_moves(b):
    return sorted(b.legal_moves, key=lambda m: (not b.is_capture(m), not b.gives_check(m)))


def search(b, depth, alpha, beta):
    """黒(CPU)が最小化、白が最大化するミニマックス + αβ。"""
    if depth == 0 or b.is_game_over():
        return evaluate(b)
    if b.turn == chess.WHITE:
        best = -10**9
        for m in ordered_moves(b):
            b.push(m)
            best = max(best, search(b, depth - 1, alpha, beta))
            b.pop()
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    best = 10**9
    for m in ordered_moves(b):
        b.push(m)
        best = min(best, search(b, depth - 1, alpha, beta))
        b.pop()
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best


def get_cpu_move(b, diff):
    legal = list(b.legal_moves)
    if not legal:
        return None
    if diff == "Easy":
        return random.choice(legal)
    if diff == "Normal":
        captures = [m for m in legal if b.is_capture(m)]
        return random.choice(captures or legal)
    depth = DIFFICULTY_DEPTH[diff]
    scored = []
    for m in legal:
        b.push(m)
        scored.append((search(b, depth - 1, -10**9, 10**9), m))
        b.pop()
    best_score = min(s for s, _ in scored)  # CPUは黒
    return random.choice([m for s, m in scored if s == best_score])


def captured_pieces(b):
    """白・黒それぞれが取った駒の絵文字を返す。"""
    start = chess.Board()
    symbols = {chess.PAWN: "♟", chess.KNIGHT: "♞", chess.BISHOP: "♝", chess.ROOK: "♜", chess.QUEEN: "♛"}
    taken = {chess.WHITE: "", chess.BLACK: ""}
    for color in (chess.WHITE, chess.BLACK):
        for pt, sym in symbols.items():
            missing = len(start.pieces(pt, color)) - len(b.pieces(pt, color))
            taken[not color] += sym * max(0, missing)
    return taken


# --- 盤面 ---
last_move = board.peek() if board.move_stack else None
check_square = board.king(board.turn) if board.is_check() else None
svg = chess.svg.board(board=board, size=420, coordinates=True, lastmove=last_move, check=check_square)
board_col, info_col = st.columns([3, 2])
with board_col:
    st.image(svg, use_container_width=True)
with info_col:
    taken = captured_pieces(board)
    st.metric("あなたが取った駒" if mode.startswith("1人") else "白が取った駒", taken[chess.WHITE] or "—")
    st.metric("相手が取った駒" if mode.startswith("1人") else "黒が取った駒", taken[chess.BLACK] or "—")
    if board.move_stack:
        with st.expander("📜 これまでの手", expanded=False):
            replay = chess.Board()
            lines = []
            for i, m in enumerate(board.move_stack):
                san = replay.san(m)
                replay.push(m)
                lines.append(f"{i // 2 + 1}. {san}" if i % 2 == 0 else f"　　… {san}")
            st.text("\n".join(lines))

st.divider()

# --- 操作 ---
if not board.is_game_over():
    is_white = board.turn == chess.WHITE
    if mode == "2人プレイ":
        turn_name = "プレイヤー1（白）" if is_white else "プレイヤー2（黒）"
    else:
        turn_name = "あなた（白）"
    if board.is_check():
        st.error("⚠️ 王手（チェック）されています！ピンチ！")
    st.info(f"👉 **{turn_name}** の番です。動かす駒と行き先を選んでね。")

    legal = list(board.legal_moves)
    from_squares = sorted({m.from_square for m in legal})

    def from_label(sq):
        return f"{chess.square_name(sq).upper()}（{PIECE_NAMES[board.piece_type_at(sq)]}）"

    col_from, col_to = st.columns(2)
    with col_from:
        selected_from = st.selectbox(
            "1. 動かしたい駒：", from_squares, format_func=from_label,
            key=f"chess_from_{len(board.move_stack)}",
        )
    targets = sorted(m.to_square for m in legal if m.from_square == selected_from)

    def to_label(sq):
        victim = board.piece_type_at(sq)
        suffix = f"（{PIECE_NAMES[victim]}をとる）" if victim else ""
        return f"{chess.square_name(sq).upper()}{suffix}"

    with col_to:
        selected_to = st.selectbox(
            "2. 行き先：", targets, format_func=to_label,
            key=f"chess_to_{len(board.move_stack)}_{selected_from}",
        )

    if st.button("✨ 駒をうごかす！", type="primary", use_container_width=True):
        # ポーンが奥まで進んだら自動でクイーンに成る
        move = chess.Move(selected_from, selected_to)
        if move not in board.legal_moves:
            move = chess.Move(selected_from, selected_to, promotion=chess.QUEEN)
        board.push(move)

        if mode.startswith("1人") and not board.is_game_over():
            with st.spinner("🤖 CPUが考え中..."):
                cpu_move = get_cpu_move(board, difficulty)
            if cpu_move:
                board.push(cpu_move)
        st.rerun()
else:
    if board.is_checkmate():
        winner_is_white = board.turn == chess.BLACK
        if mode.startswith("1人"):
            (st.success if winner_is_white else st.error)(
                "🎉 チェックメイト！あなたの勝ち！" if winner_is_white else "👾 チェックメイト…CPUの勝ち。もう一回挑戦しよう！"
            )
        else:
            st.success(f"🎉 チェックメイト！ プレイヤー{1 if winner_is_white else 2} の勝ち！")
        if winner_is_white or not mode.startswith("1人"):
            st.balloons()
    else:
        st.info("🤝 引き分けです（ステイルメイトなど）。")
    st.caption(f"結果：{board.result()}")
    if st.button("🔄 もう一度あそぶ", type="primary", use_container_width=True):
        st.session_state.chess_board = chess.Board()
        st.rerun()
