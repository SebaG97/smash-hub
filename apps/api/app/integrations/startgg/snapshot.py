"""Validated, minimal provider snapshot; no contact details or account profiles."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.integrations.startgg.client import ImportFailure


class ExternalModel(BaseModel):
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def identifier(cls, value):
        if value is None or isinstance(value, bool) or not str(value) or len(str(value)) > 150:
            raise ValueError("Invalid provider identifier")
        return str(value)


class Identity(ExternalModel):
    pass


class Participant(ExternalModel):
    gamerTag: str = Field(min_length=1, max_length=120)
    player: Identity | None = None


class Entrant(ExternalModel):
    name: str = Field(min_length=1, max_length=200)
    initialSeedNum: int | None = Field(default=None, gt=0)
    participants: list[Participant]


class Game(ExternalModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str | None = None


class Standing(ExternalModel):
    placement: int | None = Field(default=None, gt=0)
    isFinal: bool | None = None
    entrant: Identity | None = None


class Slot(BaseModel):
    slotIndex: int | None = None
    prereqId: str | None = None
    prereqType: str | None = None
    prereqPlacement: int | None = None
    entrant: Identity | None = None
    standing: dict[str, Any] | None = None


class Result(ExternalModel):
    state: int | None = None
    round: int | None = None
    startedAt: int | None = None
    hasPlaceholder: bool | None = None
    phaseGroup: dict[str, Any] | None = None
    fullRoundText: str | None = Field(default=None, max_length=100)
    completedAt: int | None = None
    updatedAt: int | None = None
    winnerId: int | str | None = None
    displayScore: str | None = None
    slots: list[Slot] = Field(max_length=2)
    # Per-game character selections; kept out of the result fingerprint.
    games: list[dict[str, Any]] | None = None


class Event(ExternalModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    state: str | None = None
    type: int | None = None
    numEntrants: int | None = Field(default=None, ge=0)
    teamRosterSize: dict[str, int | None] | None = None
    videogame: Game
    entrants: list[Entrant]
    standings: list[Standing]
    sets: list[Result]

    def team_size(self):
        roster = self.teamRosterSize
        if roster:
            low, high = roster.get("minPlayers"), roster.get("maxPlayers")
            if low is None or low != high or low < 1:
                raise ImportFailure("unsupported_variable_roster")
            return low
        # start.gg type=1 is singles, type=2 is teams; never parse the name.
        if self.type == 1:
            return 1
        raise ImportFailure("unknown_team_size")


class Tournament(ExternalModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str
    startAt: int | None = None
    endAt: int | None = None
    state: int | None = None
    city: str | None = None
    countryCode: str | None = None
    events: list[Identity]


class Snapshot(BaseModel):
    tournament: Tournament
    participants: list[Participant]
    events: list[Event]

    def validate_complete(self):
        def unique(items):
            if len({v.id for v in items}) != len(items):
                raise ImportFailure("duplicate_provider_identifier")

        unique(self.participants)
        unique(self.events)
        if not self.events:
            raise ImportFailure("no_valid_events")
        if {e.id for e in self.events} != {e.id for e in self.tournament.events}:
            raise ImportFailure("incomplete_event_list")
        people = {p.id: p for p in self.participants}
        for event in self.events:
            size = event.team_size()
            unique(event.entrants)
            unique(event.sets)
            used = set()
            for entrant in event.entrants:
                if len(entrant.participants) != size:
                    raise ImportFailure("invalid_entrant_roster")
                for person in entrant.participants:
                    if person.id not in people or person != people[person.id] or person.id in used:
                        raise ImportFailure("inconsistent_participant")
                    used.add(person.id)
            entrants = {e.id for e in event.entrants}
            if event.numEntrants is not None and event.numEntrants != len(entrants):
                raise ImportFailure("incomplete_entrant_list")
            for standing in event.standings:
                if standing.entrant and standing.entrant.id not in entrants:
                    raise ImportFailure("unknown_standing_entrant")
            for result in event.sets:
                ids = [slot.entrant.id for slot in result.slots if slot.entrant]
                if len(ids) != len(set(ids)) or any(i not in entrants for i in ids):
                    raise ImportFailure("unknown_set_entrant")
