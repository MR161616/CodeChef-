from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from uuid import uuid4
import random

app = FastAPI(title="Raja-Mantri-Chor-Sipahi Game Backend")

class CreateRoomRequest(BaseModel):
    roomName: str
    playerName: str


class JoinMultipleRequest(BaseModel):
    roomId: str
    playerNames: List[str]

class GuessRequest(BaseModel):
    playerId: str
    guessedPlayerId: str


class CreateRoomResponse(BaseModel):
    roomId: str
    playerId: str
    message: str


class JoinMultipleResponse(BaseModel):
    roomId: str
    added: List[Dict[str, str]]
    waitlisted: List[Dict[str, str]]
    message: str

class PlayerListResponse(BaseModel):
    roomId: str
    players: List[Dict[str, str]]
    waitlistCount: int

class AssignRolesResponse(BaseModel):
    message: str

class RoleResponse(BaseModel):
    playerId: str
    role: str

class GuessResponse(BaseModel):
    result: str
    actualChorId: str

class ResultResponse(BaseModel):
    round: int
    players: List[Dict[str, str]]

class LeaderboardResponse(BaseModel):
    leaderboard: List[Dict[str, str]]



class Player:
    def __init__(self, name: str):
        self.id = str(uuid4())
        self.name = name
        self.role: Optional[str] = None
        self.score: int = 0

class Room:
    def __init__(self, name: str, hostPlayer: Player):
        self.id = str(uuid4())
        self.name = name
        self.players: List[Player] = [hostPlayer]
        self.waitlist: List[Player] = []
        self.roles_assigned: bool = False
        self.mantri_id: Optional[str] = None
        self.chor_id: Optional[str] = None
        self.guess_submitted: bool = False
        self.guessed_player_id: Optional[str] = None
        self.round_number: int = 0


rooms: Dict[str, Room] = {}

POINTS = {
    "Raja": 1000,
    "Mantri": 800,
    "Sipahi": 500,
    "Chor": 0
}


@app.post("/room/create", response_model=CreateRoomResponse)
def create_room(data: CreateRoomRequest):
    host = Player(data.playerName)
    room = Room(data.roomName, host)
    rooms[room.id] = room

    return {
        "roomId": room.id,
        "playerId": host.id,
        "message": "Room created successfully"
    }





@app.post("/room/join-multiple", response_model=JoinMultipleResponse)
def join_multiple_players(data: JoinMultipleRequest):
    if data.roomId not in rooms:
        raise HTTPException(404, "Room not found")

    room = rooms[data.roomId]
    added = []
    waitlisted = []

    for name in data.playerNames:
        p = Player(name)
        if len(room.players) < 4:
            room.players.append(p)
            added.append({"id": p.id, "name": p.name})
        else:
            room.waitlist.append(p)
            waitlisted.append({"id": p.id, "name": p.name})

    return {
        "roomId": room.id,
        "added": added,
        "waitlisted": waitlisted,
        "message": "Players processed successfully"
    }



@app.get("/room/players/{roomId}", response_model=PlayerListResponse)
def get_players(roomId: str):
    if roomId not in rooms:
        raise HTTPException(404, "Room not found")

    room = rooms[roomId]

    return {
        "roomId": roomId,
        "players": [{"id": p.id, "name": p.name} for p in room.players],
        "waitlistCount": len(room.waitlist)
    }



@app.post("/room/assign/{roomId}", response_model=AssignRolesResponse)
def assign_roles(roomId: str):
    if roomId not in rooms:
        raise HTTPException(404, "Room not found")

    room = rooms[roomId]
    if len(room.players) != 4:
        raise HTTPException(400, "Exactly 4 players are required to start the game")

    ROLES = ["Raja", "Mantri", "Chor", "Sipahi"]
    random.shuffle(ROLES)

    for p, role in zip(room.players, ROLES):
        p.role = role
        if role == "Mantri":
            room.mantri_id = p.id
        if role == "Chor":
            room.chor_id = p.id

    room.roles_assigned = True
    room.guess_submitted = False
    room.round_number += 1

    return {"message": f"Roles assigned for round {room.round_number}"}



@app.get("/role/me/{roomId}/{playerId}", response_model=RoleResponse)
def view_role(roomId: str, playerId: str):
    if roomId not in rooms:
        raise HTTPException(404, "Room not found")

    for p in rooms[roomId].players:
        if p.id == playerId:
            return {"playerId": p.id, "role": p.role}

    raise HTTPException(404, "Player not found")



@app.post("/guess/{roomId}", response_model=GuessResponse)
def submit_guess(roomId: str, data: GuessRequest):
    if roomId not in rooms:
        raise HTTPException(404, "Room not found")

    room = rooms[roomId]

    if data.playerId != room.mantri_id:
        raise HTTPException(403, "Only Mantri can guess")

    room.guess_submitted = True
    room.guessed_player_id = data.guessedPlayerId

    correct_guess = (room.guessed_player_id == room.chor_id)

    for p in room.players:
        # Initialize missing score to 0
        if p.score is None:
            p.score = 0

        if correct_guess:
            p.score += POINTS[p.role]  # Standard points
        else:
            if p.role == "Chor":
                p.score += POINTS["Mantri"]
            elif p.role == "Mantri":
                p.score += 0
            else:
                p.score += POINTS[p.role]

    return {
        "result": "correct" if correct_guess else "incorrect",
        "actualChorId": room.chor_id
    }




@app.get("/result/{roomId}", response_model=ResultResponse)
def result(roomId: str):
    if roomId not in rooms:
        raise HTTPException(404, "Room not found")

    room = rooms[roomId]

    if not room.roles_assigned:
        raise HTTPException(400, "Roles not assigned yet")

    if not room.guess_submitted:
        raise HTTPException(400, "Mantri has not guessed yet")

    safe_players = []
    for p in room.players:
        safe_players.append({
            "id": p.id,
            "name": p.name,
            "role": p.role if p.role else "Unknown",
            "score": p.score if p.score is not None else 0
        })

    return {
        "round": room.round_number,
        "players": safe_players
    }





@app.get("/leaderboard/{roomId}", response_model=LeaderboardResponse)
def leaderboard(roomId: str):
    if roomId not in rooms:
        raise HTTPException(404, "Room not found")

    sorted_players = sorted(rooms[roomId].players, key=lambda p: p.score, reverse=True)

    return {
        "leaderboard": [
            {"id": p.id, "name": p.name, "score": p.score}
            for p in sorted_players
        ]
    }
