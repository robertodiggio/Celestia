import numpy as np
import pickle
import os
from collections import defaultdict
from celestia import Celestia, Card, TreasureDeck
from math import comb
import math

WIN_SCORE = 50
DECISION_PHASE        = 0   # il passeggero sceglie se restare o scendere
FALL_PHASE            = 1   # siamo nella fase in cui l'aeronave precipita
FORCED_LANDING_PHASE  = 2   # il giocatore sceglie se giocare la carta sbarco forzato o non fare niente
LANDING_PHASE         = 3   # il giocatore IA è sceso dall'aeronave

# ─────────────────────────────────────────────
# CLASSE GYM PER LE AZIONI PRESE DURANTE GLI STEP
# ─────────────────────────────────────────────

class CelestiaEnv():

    def __init__(self):

        self.game = None
        self.ai_player = None
        self.bot = None
        self.current_phase = DECISION_PHASE


    def get_obs(self) -> np.ndarray:
        captain = self.game.get_captain
        dadi    = self.game.dice_rolled
        candidates = [
            p for p in self.game.players
            if p.player_id != self.game.captain_id
            and p.player_id != self.ai_player.player_id
            and p.on_board
        ]
        threat = 0

        if candidates:
            target = max(candidates, key=lambda p: p.score)
            if target.score > self.ai_player.score:
                threat = 1


        ia_è_capitano = self.ai_player.player_id == self.game.captain_id

        if ia_è_capitano:

            success, _, _, _ = self.game.check_cards()
            ra = Card(value="rotta alternativa")
            j = Card(value="jetpack")
            sf = Card(value="sbarco forzato")
            only_captain_on_board = all(p.player_id == self.game.captain_id for p in self.game.players if p.on_board)

            if not success and only_captain_on_board and not self.ai_player.have_target_card(ra):

                obs = np.array([0], dtype=np.int32)

            elif not success and (self.ai_player.have_target_card(ra) or self.ai_player.have_target_card(j)):

                self.current_phase = FALL_PHASE

                captain_cards = 0
                special_cards = {"jetpack", "sbarco forzato", "rotta alternativa", "sabotaggio"}
                captain_cards = sum(1 for card in self.ai_player.hand if card.value not in special_cards)
                _, _, _, not_addressable_dangers = self.game.check_cards()
                num_not_addressable_dangers = len(not_addressable_dangers)
                white_faces = sum(1 for d in dadi if d == "nessun pericolo")
                num_addressable_dangers = self.game.how_many_dice - num_not_addressable_dangers - white_faces

                obs = np.array([
                    self.game.city_id,
                    num_not_addressable_dangers,
                    num_addressable_dangers,
                    captain_cards
                    ], dtype=np.int32)


            elif success and self.ai_player.have_target_card(sf) and candidates:

                self.current_phase = FORCED_LANDING_PHASE

                obs = np.array([
                    self.game.city_id,
                    threat
                    ], dtype=np.int32)
            
            else:

                obs = np.array([0], dtype=np.int32)

        else:

            if self.current_phase == DECISION_PHASE:

                prob = self.success_prob()
                obs = np.array([
                    self.game.city_id,
                    prob
                    ], dtype=np.int32)

            elif self.current_phase == FALL_PHASE:

                dangers = sum(1 for d in self.game.dice_rolled if d != "nessun pericolo")

                obs = np.array([
                    self.game.city_id,
                    dangers,
                    len(captain.hand)
                    ], dtype=np.int32)

            elif self.current_phase == FORCED_LANDING_PHASE:

                obs = np.array([
                    self.game.city_id,
                    threat
                    ], dtype=np.int32)

            elif self.current_phase == LANDING_PHASE:

                white_faces = sum(1 for d in dadi if d == "nessun pericolo")
                num_addressable_dangers = self.game.how_many_dice - white_faces

                obs = np.array([
                    white_faces,
                    num_addressable_dangers,
                    len(captain.hand)
                    ], dtype=np.int32)


        return obs


    def reset(self, train):
        # Inizializza una nuova partita
        #self.game      = Celestia(["AI_Player", "Bot1", "Bot2", "Bot3"], train)
        self.game      = Celestia(["AI_Player", "Bot1"], train)
        self.ai_player = self.game.players[0]
        # memorizzo la situazione dei bot e salvo il pericolo in cui non hanno avuto successo,
        # il numero di dadi che sono usciti e le carte che ha pescato da quando non ha superato il pericolo
        self.bot = {i: ["", 0, 0] for i in range(1, len(self.game.players))}

        # Prepara il primo turno: tutti a bordo, capitano lancia i dadi
        self.game.start_journey()
        self.game.player_decision()

        # Lo stato riflette il primo turno
        return self.get_obs()

    # ─────────────────────────────────────────────
    # STEP
    # ─────────────────────────────────────────────
    
    def step(self, action: int):
        reward     = 0.0
        terminated = False

        if not terminated:
            # Determina il ruolo dell'IA in questo turno
            ia_è_capitano = self.ai_player.player_id == self.game.captain_id

            if ia_è_capitano:
                reward, terminated = self.step_captain(action)
            else:
                reward, terminated = self.step_passenger(action)

        obs = self.get_obs() if not terminated else np.zeros(1, dtype=np.int32)

        return obs, reward, terminated #, False, {}


# ─────────────────────────────────────────────
# STEP PER L'IA PASSEGGERO
# ─────────────────────────────────────────────

    def step_passenger(self, action: int) -> tuple[float, bool]:
        dadi = self.game.dice_rolled
        reward     = 0.0
        terminated = False

        # ─────────────── AZIONE 0 ───────────────
        if action == 0:

            # ──────── L'IA SCENDE ────────
            if self.current_phase == DECISION_PHASE:
                # Scende e prende il tesoro della città corrente
                self.game.landing(self.ai_player)
                success, _, _, _ = self.game.check_cards()

                if not success:
                    reward = 2.0
                else:
                    reward = -2.0

                self.play_alternativeRoute_sabotage()
                success, _, _, _ = self.game.check_cards()
                if success:
                    self.current_phase = LANDING_PHASE
                else:
                    dangers = [d for d in dadi if d != "nessun pericolo"]
                    if len(set(dangers)) == 1:
                        self.bot[self.game.captain_id][0] = dangers[0]
                        self.bot[self.game.captain_id][1] = len(dangers)
                        self.bot[self.game.captain_id][2] = 0
                        #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                    for key in self.bot:
                        self.bot[key][2] += 1
                    #print("carta pescata")
                    self.game.captain_decision()
                    self.game.jetpack()
                    self.game.fall()
                    terminated = self.finish()

            # ──────── L'IA GIOCA ROTTA ALTERNATIVA ────────
            elif self.current_phase == FALL_PHASE:

                captain = self.game.get_captain
                captain_cards = len(captain.hand)
                dangers = sum(1 for d in dadi if d != "nessun pericolo")
                proportion = captain_cards / dangers
                factor = captain_cards / 8.0   # normalizzato su 8 (mano iniziale)
                # Reward combinata: proporzione * fattore_carte
                threshold = 1.5
                reward = (proportion * factor - threshold) * (1.0 + self.game.city_id * 0.5)
                self.game.play_alternative_route(self.ai_player)
                new_success, _, _, _ = self.game.check_cards()
                if new_success:
                    self.game.face_dangers()
                    self.game.next_city()
                else:
                    dangers = [d for d in dadi if d != "nessun pericolo"]
                    if len(set(dangers)) == 1:
                        self.bot[self.game.captain_id][0] = dangers[0]
                        self.bot[self.game.captain_id][1] = len(dangers)
                        self.bot[self.game.captain_id][2] = 0
                        #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                    for key in self.bot:
                        self.bot[key][2] += 1
                    #print("carta pescata")
                    self.game.jetpack()
                    self.game.fall()
                terminated = self.finish()

            # ──────── L'IA GIOCA SBARCO FORZATO ────────
            elif self.current_phase == FORCED_LANDING_PHASE:

                candidates = [
                    p for p in self.game.players
                    if p.player_id != self.game.captain_id
                    and p.player_id != self.ai_player.player_id
                    and p.on_board
                ]

                if candidates:
                    target = max(candidates, key=lambda p: p.score)
                    self.game.play_forced_landing(self.ai_player)
                    # Ha senso usarla solo se il target ha più punti dell'IA
                    if target.score > self.ai_player.score:
                        # Città totali - città corrente = quanto manca alla fine
                        # più è alto, più siamo all'inizio → far scendere ora vale di più
                        vicinanza_vittoria = 1.0 + (target.score / WIN_SCORE)

                        moltiplicatore = (1.0 + (5 - self.game.city_id) * 0.3)

                        reward = float(target.score - self.ai_player.score) * 0.5 * moltiplicatore * vicinanza_vittoria

                    else:
                        reward = -10.0

                self.play_alternativeRoute_sabotage()
                success, _, _, _ = self.game.check_cards()
                if success:
                    self.game.face_dangers()
                    self.game.next_city()
                    terminated = self.finish()
                else:
                    self.current_phase = FALL_PHASE

             # ──────── L'IA GIOCA SABOTAGGIO ────────
            elif self.current_phase == LANDING_PHASE:

                captain = self.game.get_captain
                captain_cards = len(captain.hand)
                white_faces = sum(1 for d in dadi if d == "nessun pericolo")
                num_addressable_dangers = self.game.how_many_dice - white_faces
                proportion = (captain_cards - num_addressable_dangers) / white_faces
                factor = captain_cards / 8.0   # normalizzato su 8 (mano iniziale)
                threshold = 1.5
                reward = - ((proportion * factor - threshold) * (1.0 + self.game.city_id * 0.5))
                dangers = self.game.play_sabotage(self.ai_player)
                new_success, _, _, _ = self.game.check_cards() 
                if new_success:
                    self.game.face_dangers()
                    self.game.next_city()
                    terminated = self.finish()
                    self.current_phase = LANDING_PHASE
                else:
                    if len(set(dangers)) == 1:
                        self.bot[self.game.captain_id][0] = dangers[0]
                        self.bot[self.game.captain_id][1] = len(dangers)
                        self.bot[self.game.captain_id][2] = 0
                        #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                    for key in self.bot:
                        self.bot[key][2] += 1
                    #print("carta pescata")
                    self.game.captain_decision()
                    self.game.jetpack()
                    self.game.fall()
                    terminated = self.finish()

        # ─────────────── AZIONE 1 ───────────────
        elif action == 1:

            # ──────── L'IA RIMANE A BORDO ────────
            if self.current_phase == DECISION_PHASE:
                white_faces = all(dado == "nessun pericolo" for dado in dadi)
                sf = Card(value="sbarco forzato")
                candidates = [
                    p for p in self.game.players
                    if p.player_id != self.game.captain_id
                    and p.player_id != self.ai_player.player_id
                    and p.on_board
                ]
                success, _, _, _ = self.game.check_cards()

                if success:
                    reward = 2.0
                else:
                    reward = -2.0

                if white_faces and self.ai_player.have_target_card(sf) and candidates:
                    self.current_phase = FORCED_LANDING_PHASE
                else:
                    self.play_alternativeRoute_sabotage()
                    success, _, _, _ = self.game.check_cards()
                    if success:
                        self.game.face_dangers()
                        self.game.next_city()
                        terminated = self.finish()
                    else:
                        self.current_phase = FALL_PHASE

            # ──────── L'IA GIOCA JETPACK ────────
            elif self.current_phase == FALL_PHASE:
                dangers = [d for d in dadi if d != "nessun pericolo"]
                if len(set(dangers)) == 1:
                    self.bot[self.game.captain_id][0] = dangers[0]
                    self.bot[self.game.captain_id][1] = len(dangers)
                    self.bot[self.game.captain_id][2] = 0
                    #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                for key in self.bot:
                    self.bot[key][2] += 1
                #print("carta pescata")
                reward = (self.game.city_id - 2) * 0.8
                self.game.play_jetpack(self.ai_player)
                self.game.jetpack()
                self.game.fall()
                terminated = self.finish()

            # ──────── L'IA NON ESEGUE AZIONI QUANDO SI TROVA SULL'AERONAVE────────
            elif self.current_phase == FORCED_LANDING_PHASE:
                reward = 0.0
                self.play_alternativeRoute_sabotage()
                success, _, _, _ = self.game.check_cards()
                if success:
                    self.game.face_dangers()
                    self.game.next_city()
                    terminated = self.finish()
                else:
                    self.current_phase = FALL_PHASE

            # ──────── L'IA NON ESEGUE AZIONI QUANDO HA DECISO DI SCENDERE ────────
            elif self.current_phase == LANDING_PHASE:
                reward = 0.0
                self.play_alternativeRoute_sabotage()
                success, _, _, _ = self.game.check_cards()
                if success:
                    self.game.face_dangers()
                    self.game.next_city()
                    terminated = self.finish()
                    self.current_phase = LANDING_PHASE
                else:
                    dangers = [d for d in dadi if d != "nessun pericolo"]
                    if len(set(dangers)) == 1:
                        self.bot[self.game.captain_id][0] = dangers[0]
                        self.bot[self.game.captain_id][1] = len(dangers)
                        self.bot[self.game.captain_id][2] = 0
                        #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                    for key in self.bot:
                        self.bot[key][2] += 1
                    #print("carta pescata")
                    self.game.jetpack()
                    self.game.fall()
                    terminated = self.finish()


        # ── AZIONE 2: L'IA NON ESEGUE AZIONI ────────
        elif action == 2:
            reward = 0.0
            #self.play_alternativeRoute_sabotage()
            success, _, _, _ = self.game.check_cards()
            if success:
                self.game.face_dangers()
                self.game.next_city()
            if not success:
                dangers = [d for d in dadi if d != "nessun pericolo"]
                if len(set(dangers)) == 1:
                    self.bot[self.game.captain_id][0] = dangers[0]
                    self.bot[self.game.captain_id][1] = len(dangers)
                    self.bot[self.game.captain_id][2] = 0
                    #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                for key in self.bot:
                    self.bot[key][2] += 1
                #print("carta pescata")
                self.game.captain_decision()
                self.game.jetpack()
                self.game.fall()
            terminated = self.finish()

        return reward, terminated


# ─────────────────────────────────────────────
# STEP PER L'IA CAPITANO
# ─────────────────────────────────────────────
    
    def step_captain(self, action: int) -> tuple[float, bool]:
        reward     = 0.0
        terminated = False

        # ──────── AZIONE 0 ────────
        if action == 0: 

            # ──────── L'IA GIOCA ROTTA ALTERNATIVA ────────
            if self.current_phase == FALL_PHASE:

                captain_cards = 0
                special_cards = {"jetpack", "sbarco forzato", "rotta alternativa", "sabotaggio"}
                captain_cards = sum(1 for card in self.ai_player.hand if card.value not in special_cards)
                _, _, _, not_addressable_dangers = self.game.check_cards()
                num_not_addressable_dangers = len(not_addressable_dangers)
                white_faces = sum(1 for d in self.game.dice_rolled if d == "nessun pericolo")
                num_addressable_dangers = self.game.how_many_dice - num_not_addressable_dangers - white_faces
                proportion = (captain_cards - num_addressable_dangers) / num_not_addressable_dangers
                factor = captain_cards / 8.0   # normalizzato su 8 (mano iniziale)
                threshold = 1.5
                reward = (proportion * factor - threshold) * (1.0 + self.game.city_id * 0.5)

                self.game.play_alternative_route(self.ai_player)
                new_success, _, _, _ = self.game.check_cards()
                if new_success:
                    self.game.face_dangers()
                    self.game.next_city()
                else:
                    self.game.captain_decision()
                    self.game.jetpack()
                    self.game.fall()
                terminated = self.finish()


            # ──────── L'IA GIOCA SBARCO FORZATO ────────
            elif self.current_phase == FORCED_LANDING_PHASE:

                candidates = [
                    p for p in self.game.players
                    if p.player_id != self.game.captain_id
                    and p.player_id != self.ai_player.player_id
                    and p.on_board
                ]

                if candidates:
                    target = max(candidates, key=lambda p: p.score)
                    self.game.play_forced_landing(self.ai_player)
                    # Ha senso usarla solo se il target ha più punti dell'IA
                    if target.score > self.ai_player.score:
                        # Città totali - città corrente = quanto manca alla fine
                        # più è alto, più siamo all'inizio → far scendere ora vale di più
                        vicinanza_vittoria = 1.0 + (target.score / WIN_SCORE)

                        moltiplicatore = (1.0 + (5 - self.game.city_id) * 0.3)

                        reward = float(target.score - self.ai_player.score) * 0.5 * moltiplicatore * vicinanza_vittoria

                    else:
                        reward = -10.0

                self.play_alternativeRoute_sabotage()
                success, _, _, _ = self.game.check_cards()
                if success:
                    self.game.face_dangers()
                    self.game.next_city()
                    terminated = self.finish()
                else:
                    self.current_phase = FALL_PHASE


        # ── AZIONE 1 ────────
        elif action == 1:
            
            # ──────── L'IA GIOCA JETPACK ────────
            if self.current_phase == FALL_PHASE:

                reward = (self.game.city_id - 2) * 0.8
                self.game.play_jetpack(self.ai_player)
                self.game.jetpack()
                self.game.fall()
                terminated = self.finish()

            # ──────── L'IA NON ESEGUE NESSUN AZIONE ────────
            elif self.current_phase == FORCED_LANDING_PHASE:
                reward = 0.0
                self.play_alternativeRoute_sabotage()
                success, _, _, _ = self.game.check_cards()
                if success:
                    self.game.face_dangers()
                    self.game.next_city()
                    terminated = self.finish()
                else:
                    self.current_phase = FALL_PHASE

        # ── AZIONE 2: L'IA NON ESEGUE AZIONI ────────
        elif action == 2: 

            reward = 0.0
            self.play_alternativeRoute_sabotage()
            success, _, _, _ = self.game.check_cards()
            if success:
                self.game.face_dangers()
                self.game.next_city()
            if not success:
                self.game.captain_decision()
                self.game.jetpack()
                self.game.fall()
            terminated = self.finish()

        return reward, terminated

    
    # ─────────────────────────────────────────────
    # METODI ADDIZIONALI
    # ─────────────────────────────────────────────


    def play_alternativeRoute_sabotage(self) -> None:
        while True:
            success, _ , _ , _ = self.game.check_cards()
            if success:
                if not self.game.has_sabotage_cards or not self.game.check_whiteFaces:
                    break
                self.game.sabotage()
            else:
                if not self.game.has_alternative_route_cards:
                    break
                self.game.alternative_route()

    def game_without_AI(self) -> tuple[bool, np.ndarray]:
        while True:
            success, _, _, _ = self.game.check_cards()
            if success:
                self.game.face_dangers()
                self.game.next_city()
                terminated = self.finish()
                if terminated or self.ai_player.on_board:
                    obs = self.get_obs() if not terminated else np.zeros(1, dtype=np.int32)
                    return terminated, obs
            else:
                dadi = self.game.dice_rolled
                dangers = [d for d in dadi if d != "nessun pericolo"]
                if len(set(dangers)) == 1:
                    #print(f"id del capitano: {self.game.captain_id}")
                    self.bot[self.game.captain_id][0] = dangers[0]
                    self.bot[self.game.captain_id][1] = len(dangers)
                    self.bot[self.game.captain_id][2] = 0
                    #print(f" il capitano {self.game.captain_id} ha problemi col pericolo: {self.bot[self.game.captain_id][0]}")
                for key in self.bot:
                    self.bot[key][2] += 1
                #print("carta pescata")
                self.game.captain_decision()
                self.game.jetpack()
                self.game.fall()
                terminated = self.finish()
                obs = self.get_obs() if not terminated else np.zeros(1, dtype=np.int32)
                return terminated, obs


    def captain_face_or_fall(self) -> bool:
        self.play_alternativeRoute_sabotage()
        success, _, _, _ = self.game.check_cards()

        if success:
            self.game.face_dangers()
            self.game.next_city()
        else:
            self.game.captain_decision()
            self.game.jetpack()
            self.game.fall()
        return self.finish()

    def finish(self) -> bool:
        terminated = False
        if self.game.city_id == 0:
            if self.game.check_winner:
                terminated = True
            else:
                self.game.start_journey()
                self.game.player_decision()
                self.game.forced_landing()
        else:
            self.game.start_journey()
            self.game.player_decision()
            self.game.forced_landing()
        self.current_phase = DECISION_PHASE
        return terminated

    def success_prob(self) -> int:
        # Calcola le carte disponibili per il capitano per capire se
        # se la scelta effettuata sia giusta o sbagliata
        dadi     = self.game.dice_rolled
        discard  = self.game.deck.discard
        mia_mano = self.ai_player.hand
        captain = self.game.get_captain
        d = len([dice for dice in dadi if dice != "nessun pericolo"])

        # Per ogni pericolo uscito, quante carte utili sono ancora in gioco?
        cards_in_play = {
            "bussola":           20 - sum(1 for c in discard  if c.value == "bussola") - sum(1 for c in mia_mano if c.value == "bussola"),
            "parafulmine":       18 - sum(1 for c in discard  if c.value == "parafulmine") - sum(1 for c in mia_mano if c.value == "parafulmine"),
            "corno":             16 - sum(1 for c in discard  if c.value == "corno") - sum(1 for c in mia_mano if c.value == "corno"),
            "cannone":           14 - sum(1 for c in discard  if c.value == "cannone") - sum(1 for c in mia_mano if c.value == "cannone"),
            "jetpack":           2  - sum(1 for c in discard  if c.value == "jetpack") - sum(1 for c in mia_mano if c.value == "jetpack"),
            "rotta alternativa": 2  - sum(1 for c in discard  if c.value == "rotta alternativa") - sum(1 for c in mia_mano if c.value == "rotta alternativa"),
            "sbarco forzato":    2  - sum(1 for c in discard  if c.value == "sbarco forzato") - sum(1 for c in mia_mano if c.value == "sbarco forzato"),
            "sabotaggio":        2  - sum(1 for c in discard  if c.value == "sabotaggio") - sum(1 for c in mia_mano if c.value == "sabotaggio")
        }
        turbo_in_play = 8 - sum(1 for c in discard  if c.value == "turbo") - sum(1 for c in mia_mano if c.value == "turbo")

        DANGER_TO_CARD = {
            "nuvole":     "bussola",
            "fulmini":    "parafulmine",
            "uccellacci": "corno",
            "pirati":     "cannone",
        }

        need: dict[str, int] = {}
        #cards_used = {k: 0 for k in cards_in_play}
        turbo_used = 0
        #prob_tot = 1.0
        prob_failure = 0.0
        prob_draw_success = 1.0
        n = len(captain.hand)
        N = sum(cards_in_play.values()) + turbo_in_play
        danger = self.bot[self.game.captain_id][0]
        draw_cards = self.bot[self.game.captain_id][2]
        danger_to_card = DANGER_TO_CARD.get(danger)

        for dado in dadi:
            card = DANGER_TO_CARD.get(dado)
            # se il pericolo fosse "nessun pericolo" allora non deve controllare nulla
            if card:
                need[card] = need.get(card, 0) + 1

        # Nessun pericolo → certezza
        if not need:
            return 10

        if n < d:
            return 0

        # Probabilità pari a 0 quando i pericoli che sono usciti adesso superano o eguagliano
        # il numero di pericoli precedenti per cui il bot non è riuscito a superare
        # + le carte che ha pescato da quando non ha avuto il successo precedente
        # Esempio: prima il bot capitano non aveva superato 1 dado con le nuvole
        # successivamente escono 2 dadi con le nuvole quando è nuovamente il turno da capitano dello stesso bot
        # e nel mentre ha pescato solamente 1 carta da quella caduta che ha fatto prima, allora
        # entrerà all'interno della condizione e la probabilità è 0 perchè è impossibile che riesca a superare il pericolo
        
        if need.get(danger_to_card, -1) >= self.bot[self.game.captain_id][1] + draw_cards:
            self.bot[self.game.captain_id][0] = ""
            self.bot[self.game.captain_id][1] = 0
            self.bot[self.game.captain_id][2] = 0
            return 0
        
        
        #print(f"carte che servono per i pericoli: {list(need.keys())}")
        if need.get(danger_to_card, -1) != -1:
            disp = cards_in_play[danger_to_card]
            turbo_remain = turbo_in_play
            K = disp + turbo_remain 
            prob_failure = comb(N - K, draw_cards) / comb(N, draw_cards)
            prob_draw_success = 1 - prob_failure
            self.bot[self.game.captain_id][0] = ""
            self.bot[self.game.captain_id][1] = 0
            self.bot[self.game.captain_id][2] = 0
        

        for type, num_needed in need.items():

            # Probabilità che il capitano abbia almeno k carte del tipo
            # considerando le carte già assegnate ai pericoli precedenti
            disp = cards_in_play[type]
            turbo_remain = turbo_in_play - turbo_used
            K = disp + turbo_remain   # carte utili per questo pericolo

            # P(ha almeno num_needed) = 1 - P(ha meno di num_needed)
            for j in range(num_needed):
                # P(ha esattamente j carte utili)
                # = C(K, j) * C(N-K, n-j) / C(N, n)
                if j > K or (n - j) > (N - K) or (n - j) < 0:
                    return 0
                try:
                    p = (comb(K, j) * comb(N - K, n - j)) / comb(N, n)
                    prob_failure += p
                except (ValueError, ZeroDivisionError):
                    continue

            if disp < num_needed:
                # Usa le carte disponibili + turbo per il resto
                turbo_used += max(0, num_needed - disp)

        prob_success = max(0.0, 1.0 - prob_failure)
        if prob_success > prob_draw_success:
            prob_success = prob_draw_success
        
        return math.floor(prob_success * 10 + 0.5)


# ─────────────────────────────────────────────
# CLASSE PER IL Q-LEARNING
# ─────────────────────────────────────────────


class QLearningAgent:

    def __init__(self) -> None:
        # Q-table: dizionario stato → {azione → valore}
        self.q_table: dict = defaultdict(lambda: defaultdict(float))

        self.epsilon = 1.0    # probabilità esplorazione iniziale

    def choose_action(self, obs: np.ndarray, available_actions: list) -> int:
        state = tuple(obs)

        # Epsilon-greedy: all'inizio esplora casualmente,
        # poi sfrutta sempre di più ciò che ha imparato
        if np.random.random() < self.epsilon:
            return np.random.choice(available_actions)

        # 1. Trova il valore massimo attuale tra le azioni possibili
        max_value = max(self.q_table[state][a] for a in available_actions)
        
        # 2. Crea una lista di TUTTE le azioni che hanno quel valore massimo (in caso di pareggio ce ne sarà più di una)
        best_actions = [a for a in available_actions if self.q_table[state][a] == max_value]
        
        # 3. Se c'è un pareggio, estrai a sorte tra le migliori; altrimenti prenderà l'unica azione migliore
        return np.random.choice(best_actions)

    def update(self, obs: np.ndarray, action: int, reward: float) -> None:
        stato     = tuple(obs)
        self.q_table[stato][action] += reward

    def decay_epsilon(self) -> None:
        # Riduce epsilon ad ogni episodio — esplora sempre meno
        self.epsilon = max(0.05, self.epsilon * 0.9998)

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({
                "q_table": dict(self.q_table),
                "epsilon": self.epsilon,
            }, f)
        print(f"💾 Q-table salvata in {path}")

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.q_table = defaultdict(
            lambda: defaultdict(float), data["q_table"]
        )
        self.epsilon = data["epsilon"]
        print(f"📂 Q-table caricata da {path}")
        return True

#--------------------------------------------
# ADDESTRAMENTO
#--------------------------------------------

def train(episodi: int) -> None:

    env   = CelestiaEnv()
    treasure_deck = TreasureDeck()
    agent_passenger = QLearningAgent()
    agent_captain_jetpack_alternativeRoute = QLearningAgent()
    agent_passenger_jetpack_alternativeRoute = QLearningAgent()
    agent_sabotage = QLearningAgent()
    agent_forcedLanding = QLearningAgent()

    reward_totale_passeggero = 0.0
    reward_totale_capitano   = 0.0

    save_path_passenger = "q_table_passenger.pkl"
    save_path_captain_jetpack_alternativeRoute = "q_table_captain_jetpack_alternativeRoute.pkl"
    save_path_passenger_jetpack_alternativeRoute = "q_table_passenger_jetpack_alternativeRoute.pkl"
    save_path_sabotage = "q_table_sabotage.pkl"
    save_path_forcedLanding = "q_table_forcedLanding.pkl"

    # Carica Q-table esistente per continuare l'addestramento
    agent_passenger.load(save_path_passenger)
    agent_captain_jetpack_alternativeRoute.load(save_path_captain_jetpack_alternativeRoute)
    agent_passenger_jetpack_alternativeRoute.load(save_path_passenger_jetpack_alternativeRoute)
    agent_sabotage.load(save_path_sabotage)
    agent_forcedLanding.load(save_path_forcedLanding)

    # Statistiche
    vittorie              = 0
    vittorie_per_episodio = 0
    score_totale          = 0
    score_per_episodio    = 0

    print(f"\n🤖 ADDESTRAMENTO Q-LEARNING — {episodi} episodi")
    print("=" * 55)

    for ep in range(1, episodi + 1):

        obs = env.reset(True)
        terminated = False

        while not terminated:
            success, _, _, _ = env.game.check_cards()
            ra = Card(value="rotta alternativa")
            j = Card(value="jetpack")
            s = Card(value="sabotaggio")
            sf = Card(value="sbarco forzato")
            candidates = [
                p for p in env.game.players
                if p.player_id != env.game.captain_id
                and p.player_id != env.ai_player.player_id
                and p.on_board
            ]
            ia_è_capitano = env.ai_player.player_id == env.game.captain_id
            # 1 Sceglie l'azione
            if ia_è_capitano:
                only_captain_on_board = all(p.player_id == env.game.captain_id for p in env.game.players if p.on_board)
                if env.current_phase == FORCED_LANDING_PHASE and env.ai_player.have_target_card(sf) and candidates:
                    action_list = [0,1]
                    action = agent_forcedLanding.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_forcedLanding.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra) and env.ai_player.have_target_card(j) and only_captain_on_board:
                    action_list = [0,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_captain_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra) and env.ai_player.have_target_card(j):
                    action_list = [0,1,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_captain_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra):
                    action_list = [0,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_captain_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(j):
                    action_list = [1,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_captain_jetpack_alternativeRoute.update(obs, action, reward)
                else:
                    terminated = env.captain_face_or_fall()
                    action = -1
            else:
                if env.current_phase == FORCED_LANDING_PHASE and env.ai_player.have_target_card(sf) and candidates:
                    action_list = [0,1]
                    action = agent_forcedLanding.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_forcedLanding.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra) and env.ai_player.have_target_card(j):
                    action_list = [0,1,2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_passenger_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra):
                    action_list = [0,2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_passenger_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(j):
                    action_list = [1,2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_passenger_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == FALL_PHASE:
                    action_list = [2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_passenger_jetpack_alternativeRoute.update(obs, action, reward)
                elif env.current_phase == LANDING_PHASE and success and env.ai_player.have_target_card(s) and env.game.check_whiteFaces:
                    action_list = [0,1]
                    action = agent_sabotage.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_sabotage.update(obs, action, reward)
                elif env.current_phase == LANDING_PHASE:
                    action_list = [1]
                    action = agent_sabotage.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_sabotage.update(obs, action, reward)
                else:
                    if not treasure_deck.check_cityDeck(0):
                        action_list = [1]
                    else:
                        action_list = [0,1]
                    action = agent_passenger.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                    agent_passenger.update(obs, action, reward)

            if action != -1:

                # Traccia statistiche
                if ia_è_capitano:
                    reward_totale_capitano += reward
                    #azioni_capitano[action] = azioni_capitano.get(action, 0) + 1
                else:
                    reward_totale_passeggero += reward
                    #azioni_passeggero[action] = azioni_passeggero.get(action, 0) + 1


                # Aggiorna lo stato corrente
                obs = new_obs

                # Fase in cui il giocatore non è a bordo
                if not env.ai_player.on_board and not env.ai_player.have_target_card(s):
                    terminated, obs = env.game_without_AI()

            else:
                obs = env.get_obs()

        # Fine episodio
        ai_score = env.ai_player.score
        score_totale += ai_score
        score_per_episodio += ai_score

        if env.game.check_winner:
            winners = env.game.winner()
            if env.ai_player in winners:
                vittorie += 1
                vittorie_per_episodio += 1

        agent_passenger.decay_epsilon()
        agent_captain_jetpack_alternativeRoute.decay_epsilon()
        agent_passenger_jetpack_alternativeRoute.decay_epsilon()
        agent_sabotage.decay_epsilon()
        agent_forcedLanding.decay_epsilon()

        # Log ogni 1000 episodi
        if ep % 1000 == 0:
            print(f"\nEp {ep:6d} | Score medio IA: {score_per_episodio/1000:.1f} | "
                  f"Vittorie: {vittorie_per_episodio:2d} | ε: {agent_passenger.epsilon:.3f}")
            print(f"  Reward media passeggero: "
                  f"{reward_totale_passeggero/ep:.2f}")
            print(f"  Reward media capitano:   "
                  f"{reward_totale_capitano/ep:.2f}")

            score_per_episodio= 0
            vittorie_per_episodio = 0
    
    agent_passenger.save(save_path_passenger)
    agent_captain_jetpack_alternativeRoute.save(save_path_captain_jetpack_alternativeRoute)
    agent_passenger_jetpack_alternativeRoute.save(save_path_passenger_jetpack_alternativeRoute)
    agent_sabotage.save(save_path_sabotage)
    agent_forcedLanding.save(save_path_forcedLanding)
    
    print(f"\n✅ Addestramento completato!")
    print(f"   Win rate finale: {vittorie/episodi*100:.1f}%")
    print(f"   Score medio IA:  {score_totale/episodi:.1f}")

#--------------------------------------------
# DEMO
#--------------------------------------------

def demo_ai() -> None:
    env   = CelestiaEnv()
    treasure_deck = TreasureDeck()
    agent_passenger = QLearningAgent()
    win = 0
    agent_captain_jetpack_alternativeRoute = QLearningAgent()
    agent_passenger_jetpack_alternativeRoute = QLearningAgent()
    agent_sabotage = QLearningAgent()
    agent_forcedLanding = QLearningAgent()

    save_path_passenger = "q_table_passenger.pkl"
    save_path_captain_jetpack_alternativeRoute = "q_table_captain_jetpack_alternativeRoute.pkl"
    save_path_passenger_jetpack_alternativeRoute = "q_table_passenger_jetpack_alternativeRoute.pkl"
    save_path_sabotage = "q_table_sabotage.pkl"
    save_path_forcedLanding = "q_table_forcedLanding.pkl"

    agent_passenger.load(save_path_passenger)
    agent_captain_jetpack_alternativeRoute.load(save_path_captain_jetpack_alternativeRoute)
    agent_passenger_jetpack_alternativeRoute.load(save_path_passenger_jetpack_alternativeRoute)
    agent_sabotage.load(save_path_sabotage)
    agent_forcedLanding.load(save_path_forcedLanding)

    # Nessuna esplorazione — solo strategia appresa
    agent_passenger.epsilon = 0.0
    agent_captain_jetpack_alternativeRoute.epsilon = 0.0
    agent_passenger_jetpack_alternativeRoute.epsilon = 0.0
    agent_sabotage.epsilon = 0.0
    agent_forcedLanding.epsilon = 0.0

    print("\n🎮 DIMOSTRAZIONE CON IA ADDESTRATA ESEGUITA SU 1000 PARTITE")
    print("=" * 55)

    for ep in range(1000):

        obs = env.reset(True)
        terminated = False

        while not terminated:
            success, _, _, _ = env.game.check_cards()
            ra = Card(value="rotta alternativa")
            j = Card(value="jetpack")
            s = Card(value="sabotaggio")
            sf = Card(value="sbarco forzato")
            candidates = [
                p for p in env.game.players
                if p.player_id != env.game.captain_id
                and p.player_id != env.ai_player.player_id
                and p.on_board
            ]
            ia_è_capitano = env.ai_player.player_id == env.game.captain_id
            # 1 Sceglie l'azione
            if ia_è_capitano:
                only_captain_on_board = all(p.player_id == env.game.captain_id for p in env.game.players if p.on_board)
                if env.current_phase == FORCED_LANDING_PHASE and env.ai_player.have_target_card(sf) and candidates:
                    action_list = [0,1]
                    action = agent_forcedLanding.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca sbarco forzato")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra) and env.ai_player.have_target_card(j) and only_captain_on_board:
                    action_list = [0,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca rotta alternativa")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra) and env.ai_player.have_target_card(j):
                    action_list = [0,1,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca rotta alternativa")
                    elif action == 1:
                        print("🤖🧑‍✈️ l'IA usa il jetpack")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra):
                    action_list = [0,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca rotta alternativa")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(j):
                    action_list = [1,2]
                    action = agent_captain_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 1:
                        print("🤖🧑‍✈️ l'IA usa il jetpack")
                    '''
                    new_obs, reward, terminated = env.step(action)
                else:
                    #print("🤖🧑‍✈️ l'IA affronta i pericoli o scende")
                    terminated = env.captain_face_or_fall()
                    action = -1
            else:
                if env.current_phase == FORCED_LANDING_PHASE and env.ai_player.have_target_card(sf) and candidates:
                    action_list = [0,1]
                    action = agent_forcedLanding.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca sbarco forzato")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra) and env.ai_player.have_target_card(j):
                    action_list = [0,1,2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca rotta alternativa")
                    elif action == 1:
                        print("🤖🧑‍✈️ l'IA usa il jetpack")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(ra):
                    action_list = [0,2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖🧑‍✈️ l'IA gioca rotta alternativa")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE and env.ai_player.have_target_card(j):
                    action_list = [1,2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    '''
                    if action == 1:
                        print("🤖🧑‍✈️ l'IA usa il jetpack")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == FALL_PHASE:
                    action_list = [2]
                    action = agent_passenger_jetpack_alternativeRoute.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == LANDING_PHASE and success and env.ai_player.have_target_card(s) and env.game.check_whiteFaces:
                    action_list = [0,1]
                    action = agent_sabotage.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖 l'IA usa sabotaggio")
                    '''
                    new_obs, reward, terminated = env.step(action)
                elif env.current_phase == LANDING_PHASE:
                    action_list = [1]
                    action = agent_sabotage.choose_action(obs, action_list)
                    new_obs, reward, terminated = env.step(action)
                else:
                    if not treasure_deck.check_cityDeck(0):
                        action_list = [1]
                    else:
                        action_list = [0,1]
                    action = agent_passenger.choose_action(obs, action_list)
                    '''
                    if action == 0:
                        print("🤖 l'IA scende")
                    elif action == 1:
                        print("🤖 l'IA continua il viaggio")
                    '''
                    new_obs, reward, terminated = env.step(action)


            if action != -1:

                # Aggiorna lo stato corrente
                obs = new_obs

                # Fase in cui il giocatore non è a bordo
                if not env.ai_player.on_board and not env.ai_player.have_target_card(s):
                    terminated, obs = env.game_without_AI()

            else:
                obs = env.get_obs()

        if env.game.check_winner:
            winners = env.game.winner()
            if env.ai_player in winners:
                win += 1

    #env.game.winner()
    print(f"Win rate finale: {win/10}%")

def stampa_q_table(agent, nomi_azioni: dict, max_stati: int) -> None:
    print(f"\n📊 Q-TABLE — Stati totali: {len(agent.q_table)}")
    print("=" * 80)

    for i, (stato, azioni) in enumerate(agent.q_table.items()):
        if i >= max_stati:
            print(f"\n... e altri {len(agent.q_table) - max_stati} stati")
            break

        if not azioni:
            continue

        azione_migliore = max(nomi_azioni.keys(), key=lambda a: azioni.get(a, 0.0))

        print(f"\nStato {i+1}: {[int(v) for v in stato]}")
        print(f"  Azione migliore: {nomi_azioni.get(azione_migliore, '???')}")
        for azione in sorted(nomi_azioni.keys()):
            valore = azioni.get(azione, 0.0)
            marker = " ←" if azione == azione_migliore else ""
            print(f"  action={azione} ({nomi_azioni.get(azione, '???'):20s}): "
                  f"{valore:8.3f}{marker}")


if __name__ == "__main__":
    # Addestra il modello
    #train(episodi=20000)

    # Gioca una partita dimostrativa
    demo_ai()

    # Analizza cosa ha imparato
    '''
    nomi_azioni_passeggero = {
            0: "scendi",
            1: "resta",
        }
    agent_passeggero = QLearningAgent()
    agent_passeggero.load("q_table_passenger.pkl")
    stampa_q_table(agent_passeggero, nomi_azioni_passeggero, max_stati=100)
    '''