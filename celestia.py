import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

# ─────────────────────────────────────────────
# IMPOSTAZIONE DEI DADI E SCORE PER VINCERE IL GIOCO
# ─────────────────────────────────────────────

class DiceFace(Enum):
    nessun_pericolo = "nessun pericolo" 
    nuvole          = "nuvole"
    fulmini         = "fulmini"
    uccellacci      = "uccellacci"
    pirati          = "pirati"

DICE_FACES = [
    DiceFace.nessun_pericolo,
    DiceFace.nessun_pericolo,
    DiceFace.nuvole,
    DiceFace.fulmini,
    DiceFace.uccellacci,
    DiceFace.pirati
]

WIN_SCORE = 50

# ─────────────────────────────────────────────
# DADO
# ─────────────────────────────────────────────

class Dice:
    @staticmethod
    def roll() -> DiceFace:
        return random.choice(DICE_FACES)

    @staticmethod
    def roll_many(n: int) -> list[DiceFace]:
        return [Dice.roll() for _ in range(n)]


# ─────────────────────────────────────────────
# CARTE IN MANO E CARTE TESORI
# ─────────────────────────────────────────────

#Carta generica nella mano di un giocatore
@dataclass
class Card:
    value: Optional[str] = None

    def __str__(self) -> str:
        return f"[Carta: {self.value}]"

    def __repr__(self) -> str:
        return self.__str__()

@dataclass
class TreasureCard:
    points:  int

    def __str__(self) -> str:
        return f"[Punti del tesoro: {self.points}]"

    def __repr__(self) -> str:
        return self.__str__()


# ─────────────────────────────────────────────
# GIOCATORE
# ─────────────────────────────────────────────

@dataclass
class Player:
    player_id: int
    name:      str
    hand:      list[Card]             = field(default_factory=list)
    treasures: list[TreasureCard]     = field(default_factory=list)
    on_board:  bool                   = True   # è sull'aereo?

    # ── proprietà punteggio ──────────────────

    @property
    def score(self) -> int:
        return sum(t.points for t in self.treasures)

    # ── gestione mano ────────────────────────

    def have_target_card(self, card: Card) -> bool:
        if card in self.hand:
            return True
        return False

    def count_turbo_cards(self) -> int:
        return sum(1 for c in self.hand if c.value == "turbo")

    def play_card(self, card: Card) -> None:
        self.hand.remove(card)

    def add_card(self, card: Card) -> None:
        self.hand.append(card)

    def add_treasure(self, treasure: Optional[TreasureCard]) -> None:
        if treasure:
            #print(f"👤 {self.name} ha pescato una carta tesoro")
            self.treasures.append(treasure)
        #else:
            #print(f"👤 {self.name} non ha pescato la carta tesoro perchè non ci sono più carte")


# ─────────────────────────────────────────────
# MAZZO CARTE E MAZZO CARTE TESORI
# ─────────────────────────────────────────────

#Mazzo equipaggiamento/power/turbo.
class Deck:
    def __init__(self) -> None:
        self.cards: list[Card] = []
        self.discard: list[Card] = []
        self.build()
        self.shuffle()

    def build(self) -> None:
        #CARTE EQUIPAGGIAMENTO:
        #bussole:
        for _ in range(20):
            self.cards.append(Card(value="bussola"))
        #parafulmine:
        for _ in range(18):
            self.cards.append(Card(value="parafulmine"))
        #corni:
        for _ in range(16):
            self.cards.append(Card(value="corno"))
        #cannoni:
        for _ in range(14):
            self.cards.append(Card(value="cannone"))
        #CARTE POTERE
        for _ in range(2):
            self.cards.append(Card(value="sbarco forzato"))
            self.cards.append(Card(value="jetpack"))
            self.cards.append(Card(value="sabotaggio"))
            self.cards.append(Card(value="rotta alternativa"))
        #CARTE TURBO
        for _ in range(8):
            self.cards.append(Card(value="turbo"))

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self) -> Card:
        if len(self.cards) == 0:
            self.cards = self.discard[:]
            self.discard = []
            self.shuffle()
        return self.cards.pop()

    def add_to_discard(self, card: Card) -> None:
        self.discard.append(card)

    def __len__(self) -> int:
        return len(self.cards)

    def show_deck(self) -> list[Card]:
        print(f"Mazzo da ({len(self.cards)} carte):")
        print(self.cards)


#Mazzo dei tesori
class TreasureDeck():
    def __init__(self) -> None:
        self.città0: list[TreasureCard] = []
        self.città1: list[TreasureCard] = []
        self.città2: list[TreasureCard] = []
        self.città3: list[TreasureCard] = []
        self.città4: list[TreasureCard] = []
        self.città5: list[TreasureCard] = []
        self.città6: list[TreasureCard] = []
        self.città7: list[TreasureCard] = []
        self.città8: list[TreasureCard] = []
        self.build()
        self.shuffle()

    def build(self) -> None:
        #Carte con valore base per tutte le città
        for _ in range (6):
            self.città0.append(TreasureCard(points=1))
            self.città1.append(TreasureCard(points=2))
            self.città2.append(TreasureCard(points=4))
            self.città3.append(TreasureCard(points=6))
            self.città4.append(TreasureCard(points=9))
            self.città5.append(TreasureCard(points=12))
            self.città6.append(TreasureCard(points=15))
            self.città7.append(TreasureCard(points=20))
            self.città8.append(TreasureCard(points=25))
        #Carte con valori più alti
        for _ in range (3):
            self.città0.append(TreasureCard(points=2))
            self.città1.append(TreasureCard(points=4))
            self.città2.append(TreasureCard(points=6))
            self.città3.append(TreasureCard(points=9))
            self.città4.append(TreasureCard(points=12))
            self.città5.append(TreasureCard(points=15))
        #Ultimi valori per la città 0 e 1
        for _ in range (2):
            self.città0.append(TreasureCard(points=4))
            self.città1.append(TreasureCard(points=6))
        #Ultimi valori per la città 2 e 3
        self.città2.append(TreasureCard(points=9))
        self.città3.append(TreasureCard(points=12))
        

    def shuffle(self) -> None:
        random.shuffle(self.città0)
        random.shuffle(self.città1)
        random.shuffle(self.città2)
        random.shuffle(self.città3)
        random.shuffle(self.città4)
        random.shuffle(self.città5)

    def draw(self, city: int) -> Optional[TreasureCard]:
        if city == 0 and len(self.città0) > 0:
            return self.città0.pop()
        elif city == 1 and len(self.città1) > 0:
            return self.città1.pop()
        elif city == 2 and len(self.città2) > 0:
            return self.città2.pop()
        elif city == 3 and len(self.città3) > 0:
            return self.città3.pop()
        elif city == 4 and len(self.città4) > 0:
            return self.città4.pop()
        elif city == 5 and len(self.città5) > 0:
            return self.città5.pop()
        elif city == 6 and len(self.città6) > 0:
            return self.città6.pop()
        elif city == 7 and len(self.città7) > 0:
            return self.città7.pop()
        elif city == 8 and len(self.città8) > 0:
            return self.città8.pop()
        else:
            return None

    def check_cityDeck(self, city: int) -> bool:
        if city == 0 and len(self.città0) > 0:
            return True
        elif city == 1 and len(self.città1) > 0:
            return True
        elif city == 2 and len(self.città2) > 0:
            return True
        elif city == 3 and len(self.città3) > 0:
            return True
        elif city == 4 and len(self.città4) > 0:
            return True
        elif city == 5 and len(self.città5) > 0:
            return True
        elif city == 6 and len(self.città6) > 0:
            return True
        elif city == 7 and len(self.città7) > 0:
            return True
        elif city == 8 and len(self.città8) > 0:
            return True
        else:
            return False

    def show_treasureDeck(self) -> list[Card]:
        print("Mazzo dei tesori:")
        print(self.città0)
        print(self.città1)
        print(self.città2)
        print(self.città3)
        print(self.città4)
        print(self.città5)
        print(self.città6)
        print(self.città7)
        print(self.città8)


# ─────────────────────────────────────────────
# MOTORE DI GIOCO PRINCIPALE
# ─────────────────────────────────────────────

class Celestia:

    # ─────────────────────────────────────────────
    # DEFINIZIONE DELLA CLASSE
    # ─────────────────────────────────────────────

    def __init__(self, player_names: list[str], train) -> None:
        if not 2 <= len(player_names) <= 6:
            raise ValueError("Celestia si gioca in 2-6 giocatori.")

        self.players: list[Player] = [
            Player(player_id=i, name=name)
            for i, name in enumerate(player_names)
        ]
        self.train= train
        self.deck = Deck()
        self.treasure_deck = TreasureDeck()

        self.city_id                    = 0                                           # aereonave sulla prima città
        self.captain_id                 = random.randint(0, len(self.players) - 1)    # id del capitano capitano
        self.dice_rolled: list[str] = []

        # Distribuiamo le carte iniziali
        cards_per_player = 8 if len(self.players) <= 3 else 6
        for p in self.players:
            for _ in range(cards_per_player):
                card = self.deck.draw()
                p.add_card(card)

    # ─────────────────────────────────────────────
    # FASI DI GIOCO
    # ─────────────────────────────────────────────

    # INIZIO DEL VIAGGIO
    def start_journey(self) -> None:
        if not self.train:
            print("------------------------")
            print("✈️ IL VIAGGIO HA INIZIO")
            print(f"🧑‍✈️ Il capitano della nave è: {self.get_captain.name}")
            print(f"👤 I giocatori a bordo sono: {', '.join(p.name for p in self.players if p.on_board)}")
        
        dice = self.how_many_dice
        if not self.train:
            print(f"🎲 Il capitano lancia {dice} dadi dei pericoli")

        roll = Dice.roll_many(dice)
        self.dice_rolled = [d.value for d in roll]
        if not self.train:
            print(f"🎲 Il risultato del lancio è: {self.dice_rolled}")

    # DECISIONE DEI GIOCATORI
    def player_decision(self) -> None:
        captain = self.get_captain
        white_faces = all(dice == "nessun pericolo" for dice in self.dice_rolled)
        dangers = len([dice for dice in self.dice_rolled if dice != "nessun pericolo"])
        prob_stay = 0.5
        if not self.train:
            print("------------------------")
            print("👤 I PASSEGGERI SCELGONO SE CONTINUARE IL VIAGGIO")
        for p in [p for p in self.players if p.on_board and p.name != "AI_Player"]:
            if p.player_id == self.captain_id:
                continue
            if white_faces:
                prob_stay = -1
            '''
            elif len(captain.hand) <= dangers:
                prob_stay = 1
            elif len(captain.hand) in (dangers + 1, dangers * 2):
                prob_stay = 0.7 + self.city_id / 35
            elif len(captain.hand) in ((dangers * 2) + 1, dangers * 3):
                prob_stay = 0.3 + self.city_id / 35
            else:
                prob_stay = self.city_id / 35
            '''
            stay = random.random() > prob_stay
            if stay == False:
                self.landing(p)
            else:
                if not self.train:
                    print(f"👤 {p.name} continua il viaggio")

    # DECISIONE DEL CAPITANO
    def captain_decision(self) -> None:
        captain = self.get_captain
        only_captain_on_board = all(p.player_id == self.captain_id for p in self.players if p.on_board)
        if only_captain_on_board == True:
            if not self.train:
                print("------------------------")
                print("🧑‍✈️ IL CAPITANO SCENDE DALL'AERONAVE")
            self.landing(captain)

    # IL CAPITANO CONTROLLA SE RIESCE AD AFFRONTARE I PERICOLI
    def check_cards(self) -> tuple[bool, str, list[str], list[str]]:
        dice = self.how_many_dice
        captain = self.get_captain
        turbo_cards = captain.count_turbo_cards()
        temp_hand = captain.hand[:]
        not_addressable_dangers = []
        missing_equipments = []
        check = True
        for i in range(dice):
            if self.dice_rolled[i] == "nuvole":
                equipment = "bussola"
            elif self.dice_rolled[i] == "fulmini":
                equipment = "parafulmine"
            elif self.dice_rolled[i] == "uccellacci":
                equipment = "corno"
            elif self.dice_rolled[i] == "pirati":
                equipment = "cannone"
            else:
                continue

            card = next((c for c in temp_hand if c.value == equipment), None)
            if card:
                temp_hand.remove(card)
            else:
                if turbo_cards > 0:
                    turbo_cards = turbo_cards - 1
                else:
                    not_addressable_dangers.append(self.dice_rolled[i])
                    missing_equipments.append(equipment)
                    check = False

        return check, captain.name, missing_equipments, not_addressable_dangers

    # IL CAPITANO AFFRONTA I PERICOLI
    def face_dangers(self) -> None:
        dice = self.how_many_dice
        captain = self.get_captain
        turbo = Card(value = "turbo")
        if not self.train:
            print("------------------------")
            print("🧑‍✈️ IL CAPITANO AFFRONTA I PERICOLI")
            #print(f"🧑‍✈️ Il capitano ha in mano le seguenti carte: {', '.join(card.value for card in captain.hand)}")
            #print(f"le carte nella pila degli scarti e in mano al giocatore 0 sono: {', '.join(card.value for card in self.deck.discard)}")
        for i in range(dice):
            equipment = Card()
            if self.dice_rolled[i] == "nuvole":
                equipment.value = "bussola"
            elif self.dice_rolled[i] == "fulmini":
                equipment.value = "parafulmine"
            elif self.dice_rolled[i] == "uccellacci":
                equipment.value = "corno"
            elif self.dice_rolled[i] == "pirati":
                equipment.value = "cannone"
            else:
                continue
            if captain.have_target_card(equipment) == True:
                captain.play_card(equipment)
                self.deck.add_to_discard(equipment)
            else:
                captain.play_card(turbo)
                self.deck.add_to_discard(turbo)
        if not self.train:
            print(f"🧑‍✈️ Il capitano {captain.name} ha superato tutti i pericoli")

    def next_city(self) -> None:
        # spostamento verso la prossima città
        if not self.train:
            print("------------------------")
            print("✈️  L'AERONAVE SI SPOSTA VERSO LA PROSSIMA CITTÀ")
        while self.city_id < 8:
            self.city_id += 1
            if self.treasure_deck.check_cityDeck(self.city_id):
                break
        if not self.train:
            print(f"Città {self.city_id} raggiunta")
        if self.city_id == 8:
            if not self.train:
                print("✈️ l'aeronave ha raggiunto l'ultima città: Meiji, la Città delle Luci")
            for p in self.players:
                if p.on_board:
                    self.landing(p)
            self.fall()
        # il capitano passa il timone ad un altro giocatore
        else:
            self.next_captain()

    def fall(self) -> None:
        self.city_id = 0
        captain = self.get_captain
        if not self.train:
            print(f"👤 tutti i giocatori pescano una carta equipaggiamento e tornano a bordo dell'aeronave per cominciare un nuovo viaggio")
            #print(f"🧑‍✈️ Il capitano aveva in mano le seguenti carte: {', '.join(card.value for card in captain.hand)}")
        for p in self.players:
            card = self.deck.draw()
            p.add_card(card)
            p.on_board = True
        self.next_captain()


    # ─────────────────────────────────────────────
    # MECCANICA DELLE CARTE ENERGIA 
    # ─────────────────────────────────────────────

    # IL GIOCATORE, O IL CAPITANO, GIOCA LA CARTA SBARCO FORZATO
    def forced_landing(self) -> None:
        sf = Card(value = "sbarco forzato")
        for p in [p for p in self.players if p.name != "AI_Player"]:
            if p.have_target_card(sf) == True and p.on_board:
                self.play_forced_landing(p)


    def play_forced_landing(self, p: Player) -> None:
        sf = Card(value = "sbarco forzato")
        if not self.train:
            print("------------------------")
            print("⚓ VIENE GIOCATA LA CARTA SBARCO FORZATO")
        candidates = [
            pob for pob in self.players
            if pob.player_id != self.captain_id
            and pob.player_id != p.player_id
            and pob.on_board
        ]
        if not candidates:
            if not self.train:
                print("⚠️ Nessun giocatore disponibile per lo sbarco forzato")
            return
        target = max(candidates, key=lambda p: p.score)
        p.play_card(sf)
        self.deck.add_to_discard(sf)
        if not self.train:
            print(f"👤 {p.name} ha utilizzato la carta sbarco forzato per far sbarcare {target.name}")
        self.landing(target)

    #IL GIOCATORE, O IL CAPITANO, GIOCA LA CARTA ROTTA ALTERNATIVA
    def alternative_route(self) -> None:
        ra = Card(value = "rotta alternativa")
        for p in [p for p in self.players if p.name != "AI_Player"]:
            if p.have_target_card(ra) == True and p.on_board:
                self.play_alternative_route(p)
                break


    def play_alternative_route(self, p: Player) -> None:
        ra = Card(value = "rotta alternativa")
        captain = self.get_captain
        dice = self.how_many_dice
        equipment = Card()
        if not self.train:
            print("------------------------")
            print("☸️  VIENE GIOCATA LA CARTA ROTTA ALTERNATIVA")
        p.play_card(ra)
        self.deck.add_to_discard(ra)
        if not self.train:
            print(f"👤 {p.name} gioca la carta rotta alternativa per far rilanciare i dadi al capitano")
        for i in range(dice):
            if self.dice_rolled[i] == "nuvole":
                equipment.value = "bussola"
            elif self.dice_rolled[i] == "fulmini":
                equipment.value = "parafulmine"
            elif self.dice_rolled[i] == "uccellacci":
                equipment.value = "corno"
            elif self.dice_rolled[i] == "pirati":
                equipment.value = "cannone"
            else:
                continue
            if captain.have_target_card(equipment) == False:
                if not self.train:
                    print(f"🧑‍✈️ Il capitano {captain.name} rilancia il dado: {self.dice_rolled[i]}")
                self.dice_rolled[i] = Dice.roll().value
                if not self.train:
                    print(f"🎲 il risultato del lancio è: {self.dice_rolled[i]}")
                    


    #IL GIOCATORE CHE NON SI TROVA A BORDO DELL'AERONAVE GIOCA LA CARTA SABOTAGGIO
    def sabotage(self) -> None:
        s = Card(value = "sabotaggio")
        for p in [p for p in self.players if p.name != "AI_Player"]:
            if p.have_target_card(s) == True and not p.on_board:
                _ = self.play_sabotage(p)
                break

    def play_sabotage(self, p: Player) -> list[str]:
        dice = self.how_many_dice
        captain = self.get_captain
        s = Card(value = "sabotaggio")
        danger: list[str] = []
        if not self.train:
            print("------------------------")
            print("💨 VIENE GIOCATA LA CARTA SABOTAGGIO")
        p.play_card(s)
        self.deck.add_to_discard(s)
        if not self.train:
            print(f"👤 {p.name} gioca la carta sabotaggio per far rilanciare i dadi bianchi al capitano")
        for i in range(dice):
            if self.dice_rolled[i] == "nessun pericolo":
                if not self.train:
                    print(f"🧑‍✈️ Il capitano {captain.name} rilancia il dado: {self.dice_rolled[i]}")
                self.dice_rolled[i] = Dice.roll().value
                if not self.train:
                    print(f"🎲 il risultato del lancio è: {self.dice_rolled[i]}")
                if self.dice_rolled[i] != "nessun pericolo":
                    danger.append(self.dice_rolled[i])
        return danger

    #IL GIOCATORE, O IL CAPITANO, GIOCA LA CARTA JETPACK
    def jetpack(self) -> None:
        j = Card(value = "jetpack")
        for p in [p for p in self.players if p.name != "AI_Player"]:
            if p.have_target_card(j) == True and p.on_board:
                self.play_jetpack(p)

    def play_jetpack(self, p: Player) -> None:
        j = Card(value = "jetpack")
        if not self.train:
            print("------------------------")
            print("🚀 VIENE GIOCATA LA CARTA JETPACK")
        p.play_card(j)
        self.deck.add_to_discard(j)
        if not self.train:
            print(f"👤 {p.name} gioca la carta jetpack per scendere poco prima che l'aeronave precipiti")
        self.landing(p)

    # ─────────────────────────────────────────────
    # METODI UTILIZZATI PER LE FASI DI GIOCO
    # ─────────────────────────────────────────────

    def landing(self, player: Player) -> None:
        player.on_board = False
        if not self.train and player.name != "AI_Player":
            print(f"👤 {player.name} scende dall'aeronave")
        treasure = self.treasure_deck.draw(self.city_id)
        player.add_treasure(treasure)

    @property
    def how_many_dice(self) -> int:
        if self.city_id in range(0,3):
            return 2
        elif self.city_id in range(3,6):
            return 3
        else:
            return 4

    @property
    def get_captain(self) -> Player:
        for p in self.players:
            if p.player_id == self.captain_id:
                return p
        raise ValueError(f"Capitano {self.captain_id} non trovato.")

    def next_captain(self) -> None:
        players_on_board = [p for p in self.players if p.on_board]
        # Cerca il prossimo player_id disponibile partendo da captain_id + 1
        n = len(self.players)
        for i in range(1, n + 1):
            next_id = (self.captain_id + i) % n
            # Controlla se esiste un giocatore a bordo con questo player_id
            candidate = next((p for p in players_on_board if p.player_id == next_id), None)
            if candidate:
                self.captain_id = candidate.player_id
                if not self.train:
                    print(f"🧑‍✈️ Il nuovo capitano è {candidate.name}")
                return
        #print(f"🧑‍✈️ Il nuovo capitano è {captain.name}")

    @property
    def check_whiteFaces(self) -> bool:
        dice = self.how_many_dice
        for i in range(dice):
            if self.dice_rolled[i] == "nessun pericolo":
                return True
        return False

    @property
    def has_sabotage_cards(self) -> bool:
        s = Card(value = "sabotaggio")
        for p in [p for p in self.players if p.name != "AI_Player"]:
            if p.have_target_card(s) == True and not p.on_board:
                return True
        return False

    @property
    def has_alternative_route_cards(self) -> bool:
        ra = Card(value = "rotta alternativa")
        for p in [p for p in self.players if p.name != "AI_Player"]:
            if p.have_target_card(ra) == True and p.on_board:
                return True
        return False

    @property
    def check_winner(self) -> bool:
        if self.city_id == 0:
            for p in self.players:
                if p.score >= WIN_SCORE:
                    return True
        return False

    def winner(self) -> list[Player]:
        max_score = max(p.score for p in self.players)
        winners = [p for p in self.players if p.score == max_score]
        if not self.train:
            print("------------------------")
            print("LA PARTITA È CONCLUSA")
        if len(winners) == 1:
            if not self.train:
                print(f"🏆 Ha vinto: {winners[0].name} con {max_score} punti!")
        else:
            if not self.train:
                names = ", ".join(p.name for p in winners)
                print(f"🤝 Pareggio tra {names} con {max_score} punti!")
        return winners
                

# ─────────────────────────────────────────────
# SIMULAZIONE DEMO (gioco terminale completo)
# ─────────────────────────────────────────────

def demo(player_names: list[str]) -> None:
    game = Celestia(player_names, False)
    print("╔══════════════════════════════════════════╗")
    print("║          CELESTIA - Demo partita         ║")
    print("╚══════════════════════════════════════════╝")
    while(game.check_winner == False):
        game.start_journey()
        game.player_decision()
        game.forced_landing()

        while True:
            print("------------------------")
            print("🔍 IL CAPITANO VEDE SE RIESCE AD AFFRONTARE I PERICOLI")
            success, _ , _ , _ = game.check_cards()
            if success:
                if not game.has_sabotage_cards or not game.check_whiteFaces:
                    break
                game.sabotage()
            else:
                if not game.has_alternative_route_cards:
                    break
                game.alternative_route()

        success, captain_name, equipment, danger = game.check_cards()
        if success:
            print(f"🧑‍✈️ Il capitano {captain_name} ha le carte necessarie per affrontare i pericoli")
            game.face_dangers()
            game.next_city()
        else:
            print(f"🧑‍✈️ Il capitano {captain_name} non ha le carte: {', '.join(equipment)}, per superare i pericoli: {', '.join(danger)}")
            game.captain_decision()
            game.jetpack()
            print("------------------------")
            print("✈️ L'AERONAVE PRECIPITA")
            game.fall()

    _ = game.winner()
    winners = game.winner()
    if game.players[0] in winners:
        return 1
    else:
        return 0

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    win = 0
    for ep in range(1):
        win += demo(["Bot1", "Bot2", "Bot3", "Bot4"])
    #print(f"Win rate finale: {win/10}%")