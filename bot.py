import berserk
import chess
import chess.polyglot
import time
import threading
import subprocess

# =========================
# LICHESS API
# =========================
LICHESS_API_TOKEN = "TWÓJ_TOKEN_TUTAJ"

client = berserk.Client(berserk.TokenSession(LICHESS_API_TOKEN))
bot_id = client.account.get()["id"]
print("Bot ID:", bot_id)

# =========================
# START ENGINE
# =========================
engine = subprocess.Popen(
    ["engine.exe"],
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

def get_engine_move(board, game_id):
    # 1. Natychmiastowy mat w 1 ruchu
    mate_move = find_mate_in_one(board)
    if mate_move:
        print("DEBUG: Znaleziono mata w 1! Wysyłam natychmiast.")
        return mate_move.uci()

    moves_played = len(board.move_stack)
    
    # --- DYNAMICZNE ZARZĄDZANIE GŁĘBOKOŚCIĄ ---
    depth = 6  # Zwiększony domyślny bazowy depth
    
    try:
        # --- 1. PRIORYTET: SZYBKI START (Pierwsze 10 ruchów bota) ---
        if moves_played < 20:
            depth = 6
            print(f"DEBUG: Szybki start (półruch {moves_played}) -> Depth: 6")
        
        # --- 2. JEŚLI NIE DEBIUT, SPRAWDZAMY CZAS ---
        else:
            game_status = client.games.get_ongoing()
            current_game = next((g for g in game_status if g['gameId'] == game_id), None)
            
            if current_game:
                my_time = current_game['secondsLeft']
                
                # Twoje progi czasowe (zostawiamy je, bo są dobre)
                if my_time > 300:
                    depth = 8
                elif my_time > 120:
                    depth = 7
                elif my_time > 15:
                    depth = 6
                else:
                    depth = 4
                
                # Bonus za końcówkę
                occupied_mask = int(board.occupied)
                piece_count = bin(occupied_mask).count('1') 
                if piece_count <= 12 and my_time > 15:
                    depth += 2
                    print(f"DEBUG: Końcówka ({piece_count} bierek) -> Bonus +1 do Depth: {depth}")

                print(f"DEBUG: Czas: {my_time}s -> Ustawiam Depth: {depth}")
            else:
                depth = 7
    except Exception as e:
        print(f"DEBUG: Błąd pobierania czasu ({e}), zostaję przy depth 7")
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
        # W nowszych wersjach berserk room podaje się bez słowa kluczowego lub inaczej
        # Spróbujmy najbardziej standardowej formy:
        client.bots.post_message(game_id, message) 
    except Exception as e:
        print(f"DEBUG: Nie udało się wysłać wiadomości: {e}")

# =========================
# OBSŁUGA PARTII
# =========================
def handle_game(game_id):
    # Tworzymy pustą planszę, zostanie ustawiona w gameFull
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
                
                # POPRAWKA: Obsługa słowa "startpos" ze strony Lichess
                raw_fen = event.get("initialFen", "startpos")
                if raw_fen == "startpos":
                    initial_fen = chess.STARTING_FEN
                else:
                    initial_fen = raw_fen
                
                board = chess.Board(initial_fen)
                
                moves = event["state"]["moves"]
                if moves:
                    for m in moves.split():
                        board.push_uci(m)

                # --- DODAJ TO TUTAJ ---
                # Sprawdź, czy po wczytaniu pozycji jest nasza tura (ważne przy wyzwaniach z FEN)
                if my_color is not None and board.turn == my_color and not board.is_game_over():
                    move_uci = get_engine_move(board, game_id)
                    try:
                        client.bots.make_move(game_id, move_uci)
                    except Exception as e:
                        print(f"Błąd ruchu startowego: {e}")
                # -----------------------

            elif event["type"] == "gameState":
                status = event.get("status")
                if status in ["mate", "resign", "outoftime", "draw", "stalemate"]:
                    if not game_ended_sent:
                        send_chat_message(game_id, "Good game! Thanks for playing!")
                        game_ended_sent = True

                # AKTUALIZACJA PLANSZY: Zawsze od FEN-u startowego tej partii!
                board = chess.Board(initial_fen)
                moves = event["moves"]
                if moves:
                    for m in moves.split():
                        board.push_uci(m)

                # RUCH BOTA: Tylko jeśli nasza kolej i gra trwa
                if my_color is not None and board.turn == my_color and not board.is_game_over():
                    move_uci = get_engine_move(board, game_id)
                    try:
                        client.bots.make_move(game_id, move_uci)
                    except Exception as e:
                        # Nie drukuj błędu jeśli to po prostu "nie twój ruch"
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