import os
import berserk
import chess
import chess.polyglot
import time
import threading
import subprocess

# =========================
# LICHESS API
# =========================
LICHESS_API_TOKEN = os.getenv("LICHESS_TOKEN")

client = berserk.Client(berserk.TokenSession(LICHESS_API_TOKEN))
bot_id = client.account.get()["id"]
print("Bot ID:", bot_id)

# =========================
# LIMIT GIER
# =========================
MAX_GAMES = 2
active_games = set()
lock = threading.Lock()

def find_mate_in_one(board):
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return move
        board.pop()
    return None

def get_engine_move(board, game_id, engine):
    mate_move = find_mate_in_one(board)
    if mate_move:
        return mate_move.uci()

    moves_played = len(board.move_stack)
    depth = 6
    
    try:
        if moves_played < 20:
            depth = 6
        else:
            game_status = client.games.get_ongoing()
            current_game = next((g for g in game_status if g['gameId'] == game_id), None)
            
            if current_game:
                my_time = current_game['secondsLeft']
                
                if my_time > 300:
                    depth = 8
                elif my_time > 120:
                    depth = 7
                elif my_time > 15:
                    depth = 6
                else:
                    depth = 4
                
                occupied_mask = int(board.occupied)
                piece_count = bin(occupied_mask).count('1') 
                
                if my_time > 15:
                    if piece_count <= 5:
                        depth += 3
                    elif piece_count <= 12:
                        depth += 1
            else:
                depth = 7
    except:
        depth = 7

    fen = board.fen()
    engine.stdin.write(f"position fen {fen}\n")
    engine.stdin.write(f"go depth {depth}\n")
    engine.stdin.flush()

    while True:
        line = engine.stdout.readline().strip()
        if "bestmove" in line:
            return line.split()[1]

def send_chat_message(game_id, message):
    try:
        client.bots.post_message(game_id, message) 
    except:
        pass

# =========================
# OBSŁUGA PARTII
# =========================
def handle_game(game_id):
    with lock:
        active_games.add(game_id)

    # 🔥 NOWY SILNIK NA PARTIĘ
    engine = subprocess.Popen(
        ["./engine"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True
    )

    board = chess.Board()
    initial_fen = chess.STARTING_FEN
    game_ended_sent = False
    
    try:
        stream = client.bots.stream_game_state(game_id)
        last_event_time = time.time()
        my_color = None

        for event in stream:
            last_event_time = time.time()

            if event["type"] == "gameFull":
                send_chat_message(game_id, "Hi! I'm PawelBot, good luck!")
                
                white_id = event["white"]["id"]
                my_color = chess.WHITE if white_id == bot_id else chess.BLACK
                
                raw_fen = event.get("initialFen", "startpos")
                initial_fen = chess.STARTING_FEN if raw_fen == "startpos" else raw_fen
                
                board = chess.Board(initial_fen)
                
                moves = event["state"]["moves"]
                if moves:
                    for m in moves.split():
                        board.push_uci(m)

                if my_color is not None and board.turn == my_color and not board.is_game_over():
                    move_uci = get_engine_move(board, game_id, engine)
                    try:
                        client.bots.make_move(game_id, move_uci)
                    except Exception as e:
                        print(f"Błąd ruchu startowego: {e}")

            elif event["type"] == "gameState":
                status = event.get("status")
                if status in ["mate", "resign", "outoftime", "draw", "stalemate"]:
                    if not game_ended_sent:
                        send_chat_message(game_id, "Good game!")
                        game_ended_sent = True

                board = chess.Board(initial_fen)
                moves = event["moves"]
                if moves:
                    for m in moves.split():
                        board.push_uci(m)

                if my_color is not None and board.turn == my_color and not board.is_game_over():
                    move_uci = get_engine_move(board, game_id, engine)
                    try:
                        client.bots.make_move(game_id, move_uci)
                    except Exception as e:
                        if "Not your turn" not in str(e):
                            print(f"Błąd ruchu: {e}")

            # timeout
            if time.time() - last_event_time > 30:
                print("Timeout gry - restart")
                break
                            
    except Exception as e:
        print(f"Partia przerwana: {e}")

    finally:
        engine.kill()
        with lock:
            active_games.discard(game_id)

# =========================
# STREAM WYZWAN
# =========================
def main():
    print("Bot działa...")

    while True:
        try:
            for event in client.bots.stream_incoming_events():

                if event["type"] == "challenge":
                    with lock:
                        if len(active_games) >= MAX_GAMES:
                            print("Limit gier osiągnięty - odrzucam")
                            client.bots.decline_challenge(event["challenge"]["id"])
                            continue

                    try:
                        client.bots.accept_challenge(event["challenge"]["id"])
                        print("Przyjęto wyzwanie")
                    except:
                        print("Błąd accept")

                elif event["type"] == "gameStart":
                    game_id = event["game"]["id"]
                    threading.Thread(
                        target=handle_game,
                        args=(game_id,),
                        daemon=True
                    ).start()

        except Exception as e:
            print(f"Stream padł: {e}")
            time.sleep(5)

# =========================
# AUTO-RESTART
# =========================
if __name__ == "__main__":
    while True:
        try:
            print("=== START BOTA ===")
            main()
        except Exception as e:
            print(f"CRASH: {e}")
            time.sleep(5)
