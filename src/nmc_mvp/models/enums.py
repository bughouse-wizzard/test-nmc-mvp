from enum import Enum


class SearchStatus(str, Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class InputSource(str, Enum):
    MANUAL = "MANUAL"
    FILE = "FILE"


class MatchType(str, Enum):
    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"


class MatchStatus(str, Enum):
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"