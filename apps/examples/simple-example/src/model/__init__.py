"""
Data model for simple-example test application
"""
from datetime import datetime
from typing import List, Optional
from enum import Enum
# from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field

from hopeit.dataobjects import dataobject


class StatusType(str, Enum):
    NEW = 'NEW'
    LOADED = 'LOADED'
    SUBMITTED = 'SUBMITTED'
    PROCESSED = 'PROCESSED'


@dataobject
class Status(BaseModel):
    """Status change"""
    ts: datetime
    type: StatusType


@dataobject
class User(BaseModel):
    """User information"""
    id: str
    name: str


@dataobject(event_id='id', event_ts='status.ts')
class Something(BaseModel):
    """Example Something event"""
    id: str
    user: User
    status: Optional[Status] = None
    history: List[Status] = Field(default_factory=list)


@dataobject
class SomethingParams(BaseModel):
    """Params to create and save Something"""
    id: str
    user: str


@dataobject
class SomethingNotFound(BaseModel):
    """Item not found in datastore"""
    path: str
    id: str


@dataobject
class ItemsInfo(BaseModel):
    """
    Items to read concurrently
    """
    item1_id: str
    item2_id: str
    partition_key: str = ""


@dataobject(event_id='payload.id', event_ts='payload.status.ts')
class SomethingStored(BaseModel):
    path: str
    payload: Something
