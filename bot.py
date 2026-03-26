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
# START ENGINE
# =========================
engine = subprocess.Popen(
    ["./engine"], 
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

def find_mate_in_one(board):
    """Sprawdza, czy jest mat w 1 ruchu przed zapytaniem silnika."""
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return move
        board.pop()
    return None

# POPRAWKA: Dodajemy parametr my_time, żeby nie pytać o niego API Lichessa
def get_engine_move(board, game_id, my_time):
    # 1. Natychmiastowy mat w 1 ruchu
    mate_move = find_mate_in_one(board)
    if mate_move:
        print("DEBUG: Znaleziono mata w 1! Wysyłam natychmiast.")
        return mate_move.uci()

    moves_played = len(board.move_stack)
    
    # --- DYNAMICZNE ZARZĄDZANIE GŁĘBOKOŚCIĄ ---
    depth = 6  
    
    try:
        if moves_played < 20:
            depth = 6
            print(f"DEBUG: Szybki start (półruch {moves_played}) -> Depth: 6")
        else:
            # USUNIĘTO: client.games.get_ongoing() - to spowalniało bota
            if my_time is not None:
                # Twoje progi czasowe
                if my_time > 300:
                    depth = 8
                elif my_time > 120:
                    depth = 7
                elif my_time > 15:
                    depth = 6
                else:
                    depth = 4
                
                # --- DYNAMICZNY BONUS ZA KOŃCÓWKĘ ---
                occupied_mask = int(board.occupied)
                piece_count = bin(occupied_mask).count('1') 
                
                if my_time > 15:  
                    if piece_count <= 5:
                        depth += 3
                        print(f"DEBUG: Głęboka końcówka ({piece_count} bierek) -> Super Bonus +3")
                    elif piece_count <= 12:
                        depth += 1
                        print(f"DEBUG: Końcówka ({piece_count} bierek) -> Bonus +1")

                print(f"DEBUG: Czas: {my_time}s -> Ustawiam Depth: {depth}")
            else:
                depth = 7
    except Exception as e:
        print(f"DEBUG: Błąd logiki czasu ({e}), zostaję przy depth 7")
        depth = 7

    # 2. Wysyłanie do silnika
    fen = board.fen()
    history_hashes = []
    temp_board = board.copy()
    for _ in range(min(len(board.move_stack), 6)):
        history_hashes.append(str(chess.polyglot.zobrist_hash(temp_board)))
        try:
            temp_board.pop()
        except:
            break
    
    hashes_str = " ".join(history_hashes)
    
    engine.stdin.write(f"position fen {fen} hashes {hashes_str}\n")
    engine.stdin.write(f"go depth {depth}\n")
    engine.stdin.flush()

    while True:
        line = engine.stdout.readline().strip()
        if "bestmove" in line:
            return line.split()[1]

def send_chat_message(game_id, message):
    try:
        client.bots.post_message(game_id, message) 
    except Exception as e:
        print(f"DEBUG: Nie udało się wysłać wiadomości: {e}")

# =========================
# OBSŁUGA PARTII
# =========================
def handle_game(game_id):
    board = chess.Board()
    initial_fen = chess.STARTING_FEN
    game_ended_sent = False
    
    try:
        stream = client.bots.stream_game_state(game_id)
        my_color = None

        for event in stream:
            if event["type"] == "gameFull":
                send_chat_message(game_id, "Hi! I'm PawelBot, good luck!")
                
                white_id = event["white"]["id"]
                my_color = chess.WHITE if white_id == bot_id else chess.BLACK
                
                raw_fen = event.get("initialFen", "startpos")
                initial_fen = chess.STARTING_FEN if raw_fen == "startpos" else raw_fen
                board = chess.Board(initial_fen)
                
                state = event["state"]
                moves = state["moves"]
                if moves:
                    for m in moves.split():
                        board.push_uci(m)

                if my_color is not None and board.turn == my_color and not board.is_game_over():
                    # Wyciągamy czas z eventu
                    my_time_ms = state["wtime"] if my_color == chess.WHITE else state["btime"]
                    move_uci = get_engine_move(board, game_id, my_time_ms / 1000)
                    try:
                        client.bots.make_move(game_id, move_uci)
                    except Exception as e:
                        print(f"Błąd ruchu startowego: {e}")

            elif event["type"] == "gameState":
                status = event.get("status")
                if status in ["mate", "resign", "outoftime", "draw", "stalemate"]:
                    if not game_ended_sent:
                        send_chat_message(game_id, "Good game! Thanks for playing!")
                        game_ended_sent = True

                board = chess.Board(initial_fen)
                moves = event["moves"]
                if moves:
                    for m in moves.split():
                        board.push_uci(m)

                if my_color is not None and board.turn == my_color and not board.is_game_over():
                    # POPRAWKA: Pobieramy czas bezpośrednio z gameState
                    my_time_ms = event["wtime"] if my_color == chess.WHITE else event["btime"]
                    move_uci = get_engine_move(board, game_id, my_time_ms / 1000)
                    try:
                        client.bots.make_move(game_id, move_uci)
                    except Exception as e:
                        if "Not your turn" not in str(e):
                            print(f"Błąd ruchu: {e}")
                            
    except Exception as e:
        print(f"Partia przerwana: {e}")

# =========================
# STREAM WYZWAN (GŁÓWNA PĘTLA)
# =========================
def main():
    print("PawelBot_V6 gotowy do akcji...")
    for event in client.bots.stream_incoming_events():
        if event["type"] == "challenge":
            challenge_id = event["challenge"]["id"]
            try:
                client.bots.accept_challenge(challenge_id)
                print(f"Zaakceptowano wyzwanie: {challenge_id}")
            except:
                print("Nie udało się przyjąć wyzwania.")

        elif event["type"] == "gameStart":
            game_id = event["game"]["id"]
            threading.Thread(target=handle_game, args=(game_id,), daemon=True).start()

if __name__ == "__main__":
    main()
