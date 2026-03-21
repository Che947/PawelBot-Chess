#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <sstream>
#include <algorithm>
#include <random>
#include <chrono>
#include <map>       // Dodane dla księgi otwarć
#include "chess.hpp"

using namespace chess;

Board board;
std::vector<uint64_t> position_history;
long long nodes_visited = 0;

struct TTEntry {
    int depth;
    int score;
};
std::unordered_map<uint64_t, TTEntry> transposition_table;

// Mapa przechowująca listę ruchów dla każdego FEN
std::map<std::string, std::vector<std::string>> opening_book;

void add_to_book(std::string fen, std::string move) {
    opening_book[fen].push_back(move);
}

void init_opening_book() {
    // --- BIAŁE START (4 opcje do losowania) ---
    add_to_book("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e4");
    add_to_book("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "d2d4");
    add_to_book("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "g1f3");
    add_to_book("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "c2c4");

    // --- CZARNE ODPOWIADAJĄ NA e4 (4 opcje) ---
    add_to_book("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "e7e5");
    add_to_book("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "c7c5");
    add_to_book("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "e7e6");
    add_to_book("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "c7c6");

    // --- LINIA: 1. e4 e5 (Partia Hiszpańska / Włoska) ---
    add_to_book("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "g1f3");
    add_to_book("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2", "b8c6");
    add_to_book("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3", "f1b5"); // Hiszpańska
    add_to_book("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", "a7a6"); // Morphy
    add_to_book("r1bqkbnr/1ppp1ppp/p1n5/4p3/B3P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4", "b5a4");
    add_to_book("r1bqkbnr/1ppp1ppp/p1n5/4p3/B3P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4", "O-O"); 
    
    // --- LINIA: 1. e4 c5 (Sycylijska) ---
    add_to_book("rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "g1f3");
    add_to_book("rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2", "d7d6");
    add_to_book("rnbqkbnr/pp2pppp/3p4/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3", "d2d4"); // Open
    add_to_book("rnbqkbnr/pp2pppp/3p4/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3", "c5d4");
    add_to_book("rnbqkbnr/pp2pppp/3p4/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 4", "f3d4");
    add_to_book("rnbqkbnr/pp2pppp/3p4/8/3NP3/8/PPP2PPP/RNBQKB1R b KQkq - 0 4", "g8f6");
    add_to_book("rnbqkb1r/pp2pppp/3p1n2/8/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 1 5", "b1c3");

    // --- LINIA: 1. e4 c6 (Karo-Kann) ---
    add_to_book("rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "d2d4");
    add_to_book("rnbqkbnr/pp1ppppp/2p5/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 2", "d7d5");
    add_to_book("rnbqkbnr/pp2pppp/2p5/3p4/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3", "e4e5");

    // --- BIAŁE: d4 (Odpowiedzi na d4) ---
    add_to_book("rnbqkbnr/pppppppp/8/8/3P4/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "d7d5");
    add_to_book("rnbqkbnr/pppppppp/8/8/3P4/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "g8f6");
    
    // --- LINIA: 1. d4 d5 ---
    add_to_book("rnbqkbnr/pppppppp/8/3p4/3P4/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "c2c4"); // Gambit
    add_to_book("rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2", "e7e6");
    add_to_book("rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2", "c7c6");
    add_to_book("rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2", "d5c4");

    // --- LINIA: 1. d4 Nf6 ---
    add_to_book("rnbqkb1r/pppppppp/5n2/8/3P4/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2", "c2c4");
    add_to_book("rnbqkb1r/pppppppp/5n2/8/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2", "e7e6");
    add_to_book("rnbqkb1r/pppp1ppp/4pn2/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 3", "g1f3");
    add_to_book("rnbqkb1r/pppp1ppp/4pn2/8/2PP4/5N2/PP2PPPP/RNBQKB1R b KQkq - 1 3", "b7b6");
}

// --- TABLICE PST (Nienaruszone) ---
const int pawn_pst[64] = {
    0,  0,  0,  0,  0,  0,  0,  0,
    5, 10, 10,-20,-20, 10, 10,  5,
    5, -5,-10,  0,  0,-10, -5,  5,
    0,  0,  0, 20, 20,  0,  0,  0,
    5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
    0,  0,  0,  0,  0,  0,  0,  0
};

const int knight_pst[64] = {
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
};

const int bishop_pst[64] = {
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
};

const int king_pst[64] = {
    20, 30, 10,  0,  0, 10, 30, 20,
    20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30
};

const int king_endgame_pst[64] = {
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
};

int get_move_score(const Move& m) {
    if (board.isCapture(m)) {
        int victim = (int)board.at(m.to()).type();
        int attacker = (int)board.at(m.from()).type();
        return 1000 + (victim * 10) - attacker;
    }
    return 0;
}

// --- EWALUACJA ---
int evaluate() {
    int score = 0;
    int major_pieces = 0;
    for (int i = 0; i < 64; i++) {
        auto pt = board.at(Square(i)).type();
        if (pt != PieceType::NONE && pt != PieceType::PAWN && pt != PieceType::KING) major_pieces++;
    }

    float phase = 1.0f - (std::min(major_pieces, 14) / 14.0f);

    for (int i = 0; i < 64; i++) {
        Square sq = Square(i);
        auto piece = board.at(sq);
        if (piece.type() == PieceType::NONE) continue;

        int val = 0;
        const int* pst = nullptr;
        auto pt = piece.type();
        Color c = piece.color();

        if (pt == PieceType::PAWN) { 
            val = 100; pst = pawn_pst; 
            int r = (int)sq.rank();
            int rank_bonus = (c == Color::WHITE) ? (r * r) : ((7 - r) * (7 - r));
            val += (int)(rank_bonus * (0.2f + (0.8f * phase)));
        }
        else if (pt == PieceType::KNIGHT) { val = 320; pst = knight_pst; }
        else if (pt == PieceType::BISHOP) { val = 330; pst = bishop_pst; }
        else if (pt == PieceType::ROOK)   { val = 500; }
        else if (pt == PieceType::QUEEN)  { val = 900; }
        else if (pt == PieceType::KING)   { 
            val = 20000; 
            int pst_mid = (c == Color::WHITE) ? king_pst[i] : king_pst[i ^ 56];
            int pst_end = (c == Color::WHITE) ? king_endgame_pst[i] : king_endgame_pst[i ^ 56];
            int interpolated_pst = (int)(pst_mid * (1.0f - phase) + pst_end * phase);
            score += (c == Color::WHITE) ? (val + interpolated_pst) : -(val + interpolated_pst);
            continue;
        }

        int pst_val = 0;
        if (pst) pst_val = (c == Color::WHITE) ? pst[i] : pst[i ^ 56];
        score += (c == Color::WHITE) ? (val + pst_val) : -(val + pst_val);
    }
    return score;
}

// --- ALPHABETA ---
// Główna funkcja Alpha-Beta z Transposition Table
int alphabeta(int depth, int alpha, int beta) {
    nodes_visited++;
    
    // 1. Sprawdzenie TT (Transposition Table)
    uint64_t pos_hash = board.hash();
    if (transposition_table.count(pos_hash)) {
        auto& entry = transposition_table[pos_hash];
        if (entry.depth >= depth) {
            return entry.score;
        }
    }

    Movelist moves;
    movegen::legalmoves(moves, board);
    
    if (moves.empty()) {
        if (board.inCheck()) {
            return (board.sideToMove() == Color::WHITE) ? (-1000000 - depth) : (1000000 + depth);
        }
        return 0; // Pat
    }

    if (depth <= 0) return evaluate();

    // Sortowanie ruchów (MVV-LVA) dla lepszych odcięć
    std::sort(moves.begin(), moves.end(), [](const Move& a, const Move& b) {
        return get_move_score(a) > get_move_score(b);
    });

    int best_score;
    if (board.sideToMove() == Color::WHITE) {
        best_score = -3000000;
        for (auto m : moves) {
            board.makeMove(m);
            int score = alphabeta(depth - 1, alpha, beta);
            board.unmakeMove(m);
            
            if (score > best_score) {
                best_score = score;
            }
            alpha = std::max(alpha, best_score);
            if (beta <= alpha) break; // Odcięcie Beta
        }
    } else {
        best_score = 3000000;
        for (auto m : moves) {
            board.makeMove(m);
            int score = alphabeta(depth - 1, alpha, beta);
            board.unmakeMove(m);
            
            if (score < best_score) {
                best_score = score;
            }
            beta = std::min(beta, best_score);
            if (beta <= alpha) break; // Odcięcie Alpha
        }
    }

    // 2. Zapisanie wyniku do TT przed wyjściem
    transposition_table[pos_hash] = {depth, best_score};
    return best_score;
}

// --- MAIN ---
int main() {
    std::ios::sync_with_stdio(false);
    init_opening_book(); // Wczytanie debiutów przy starcie
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line == "uci") {
            std::cout << "id name PawelBot_V14\nid author Pawel\nuciok" << std::endl;
        } else if (line == "isready") {
            std::cout << "readyok" << std::endl;
        } else if (line.find("position fen") == 0) {
            std::stringstream ss(line);
            std::string t; ss >> t >> t; // "position fen"
            std::string fen; for(int i=0; i<6; i++) { ss >> t; fen += t + " "; }
            board.setFen(fen);
            position_history.clear();
            while (ss >> t) if (t == "hashes") {
                uint64_t h; while (ss >> h) position_history.push_back(h);
            }
        } else if (line.find("go") == 0) {
            transposition_table.clear();
            std::string current_fen = board.getFen();
            
            if (opening_book.count(current_fen)) {
                std::vector<std::string>& moves = opening_book[current_fen];
                
                // Losowanie ruchu z dostępnych opcji
                static std::mt19937 gen(std::chrono::system_clock::now().time_since_epoch().count());
                std::uniform_int_distribution<> dis(0, moves.size() - 1);
                std::string chosen_move = moves[dis(gen)];

                std::cerr << "DEBUG: Ruch z ksiazki (losowy z " << moves.size() << " opcji)" << std::endl;
                std::cout << "bestmove " << chosen_move << std::endl;
                continue; 
            }

            nodes_visited = 0;
            auto start = std::chrono::high_resolution_clock::now();
            
            int depth = 6;
            size_t d_pos = line.find("depth");
            if (d_pos != std::string::npos) depth = std::stoi(line.substr(d_pos + 6));

            Movelist moves;
            movegen::legalmoves(moves, board);
            if (moves.empty()) { std::cout << "bestmove 0000" << std::endl; continue; }

            std::sort(moves.begin(), moves.end(), [](const Move& a, const Move& b) {
                return get_move_score(a) > get_move_score(b);
            });

            Color mover = board.sideToMove();
            Move best_m = moves[0];
            int best_v = (mover == Color::WHITE) ? -4000000 : 4000000;

            for (auto m : moves) {
                board.makeMove(m);
                uint64_t next_h = board.hash();
                bool repeat = false;
                for (auto h : position_history) if (h == next_h) { repeat = true; break; }

                int score = repeat ? 0 : alphabeta(depth - 1, -4000000, 4000000);
                if (repeat) score = (mover == Color::WHITE) ? -15000 : 15000;

                board.unmakeMove(m);

                if (mover == Color::WHITE) {
                    if (score > best_v) { best_v = score; best_m = m; }
                } else {
                    if (score < best_v) { best_v = score; best_m = m; }
                }
            }

            auto end = std::chrono::high_resolution_clock::now();
            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
            std::cerr << "DEBUG: Przeanalizowano " << nodes_visited << " pozycji w " << duration << "ms" << std::endl;
            std::cout << "bestmove " << uci::moveToUci(best_m) << std::endl;
        } else if (line == "quit") {
            break;
        }
    }
    return 0;
}