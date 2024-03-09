"""
DataFrames type abstractions.

Example:

    from hopeit.dataobjects import dataclass # equivalent to `dataclasses.dataclass`
    from hopeit.dataframes import dataframe

    @dataframe
    @dataclass
    class MyObject:
        name: str
        number: int
"""

from dataclasses import asdict, dataclass, fields, make_dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, Type, TypeVar
from dataclasses_jsonschema import DEFAULT_SCHEMA_TYPE, JsonSchemaMixin

import numpy as np
import pandas as pd
from hopeit.dataframes.serialization.dataset import Dataset
from hopeit.dataobjects import DataObject, StreamEventMixin, StreamEventParams, dataobject

DataFrameType = TypeVar("DataFrameType")


@dataclass
class DataFrameMetadata:
    columns: List[str]
    serialized_type: Type[DataObject]
    

@dataclass
class DataFrameParams:
    """
    Helper class used to access attributes in @dataframe
    decorated objects, based on dot notation expressions
    """

    datatypes: Optional[str]

    @staticmethod
    def extract_attr(obj, expr):
        value = obj
        for attr_name in expr.split("."):
            if value:
                value = getattr(value, attr_name)
        return value


class DataFrameMixin(Generic[DataFrameType]):
    """
    MixIn class to add functionality for DataFrames dataobjects

    Do not use this class directly, instead use `@dataframe` class decorator.
    """

    DATATYPE_MAPPING = {
        int: lambda x: x.astype(np.int64),
        float: lambda x: x.astype(np.float64),
        str: lambda x: x.astype(object),
        date: lambda x: pd.to_datetime(x),
        datetime: lambda x: pd.to_datetime(x),
    }

    def __init__(self) -> None:
        # Fields added here only to allow mypy to provide correct type hints
        self.__data_object__: Dict[str, Any] = {}
        self.__dataframe__: Dict[str, Any] = {}
        self.__df = pd.DataFrame()
        raise NotImplementedError  # must use @dataframe decorator  # pragma: no cover

    @staticmethod
    def __init_from_series__(
        self, **series: pd.Series
    ):  # pylint: disable=bad-staticmethod-argument
        df = pd.DataFrame(series)
        setattr(self, "__df", df[self.__dataframe__.columns])
        if self.__data_object__["validate"]:
            self._coerce_datatypes()

    @classmethod
    def from_df(cls, df: pd.DataFrame, **series: Any) -> DataFrameType:
        df = df if cls.__data_object__["unsafe"] else pd.DataFrame(df)
        for col, values in series.items():
            df[col] = values
        obj = cls(**df._series)  # pylint: disable=protected-access
        return obj  # type: ignore
    
    @classmethod
    def from_array(cls, array: np.array) -> DataFrameType:
        return cls.from_df(
            pd.DataFrame(
                array, columns=cls.__dataframe__.columns
            )
        )

    @classmethod
    def from_dataobjects(cls, items: Iterator[DataObject]) -> DataFrameType:
        return cls.from_df(
            pd.DataFrame(
                asdict(item) for item in items
            )
        )

    @classmethod
    def _from_df_unsafe(cls, df: pd.DataFrame, **series: pd.Series) -> DataFrameType:
        for col, values in series.items():
            df[col] = values
        obj = cls(**df._series)  # pylint: disable=protected-access
        return obj  # type: ignore

    @property
    def df(self) -> pd.DataFrame:
        return getattr(self, "__df")

    def __getitem__(self, key) -> "DataFrameType":
        return self.from_df(self.__df[key])


    def to_dataobjects(self) -> List[DataObject]:
        return [
            self.__dataframe__.serialized_type(**fields)
            for fields in self.__df.to_dict(orient="records")
        ]

    def to_json(self, *args, **kwargs) -> str:
        raise NotImplemented("Dataframe must be used inside `@dataobject(unsafe=True)` to be used as an output")

    def to_dict(self, *args, **kwargs) -> Dict[str, Any]:
        raise NotImplemented("Dataframe must be used inside `@dataobject(unsafe=True)` to be used as an output")

    @classmethod
    def from_json(cls, *args, **kwargs) -> DataObject:
        return cls.__dataframe__.serialized_type.from_dict(*args, **kwargs)

    @classmethod
    def from_dict(
        cls,
        *args,
        **kwargs,
    ) -> DataObject:
        return cls.__dataframe__.serialized_type.from_dict(*args, **kwargs)
        

    @classmethod
    def json_schema(cls, *args, **kwargs) -> Dict[str, Any]:
        schema = cls.__dataframe__.serialized_type.json_schema(*args, **kwargs)
        schema[cls.__name__] = schema[cls.__dataframe__.serialized_type.__name__]
        return schema

    def event_id(*args, **kwargs) -> None:
        return ""

    def event_ts(*args, **kwargs) -> None:
        return datetime.now(tz=timezone.utc)

    def __getattribute__(self, name: str) -> Any:
        if name[:2] == "__":
            return object.__getattribute__(self, name)
        if name in self.__dataframe__.columns:
            return self.__df[name]
        if name[:15] == "_DataFrameMixin":
            return object.__getattribute__(self, name[15:])
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.__dataframe__.columns:
            self.__df[name] = value
        else:
            object.__setattr__(self, name, value)

    def _coerce_datatypes(self):
        for field in fields(self):
            self.__df.loc[:, field.name] = self.DATATYPE_MAPPING[field.type](
                self.__df[field.name]
            )


def dataframe(
    decorated_class=None,
    unsafe: bool = False,
    validate: bool = True,
    schema: bool = True,
) -> Callable[[Type], Type[DataFrameMixin]]:
    """
    Decorator for dataclasses intended to be used as dataframes.
    """

    def add_dataframe_mixin(cls) -> Type[DataFrameMixin]:
        if hasattr(cls, "__annotations__") and hasattr(cls, "__dataclass_fields__"):
            amended_class = type(
                cls.__name__,
                (DataFrameMixin, JsonSchemaMixin) + cls.__mro__,
                dict(cls.__dict__),
                # cls.__name__, cls.__mro__, dict(cls.__dict__)
            )
            setattr(amended_class, "__init__", DataFrameMixin.__init_from_series__)
            return amended_class
        return cls

    def add_dataframe_metadata(cls):
        serialized_fiels = [
            (field.name, field.type)
            for field in fields(cls)
        ]
        serialized_type = make_dataclass(cls.__name__ + "_", serialized_fiels)
        serialized_type = dataobject(serialized_type, unsafe=True)

        setattr(
            cls,
            "__dataframe__",
            DataFrameMetadata(
                columns=[field.name for field in fields(cls)],
                serialized_type=serialized_type,
            ),
        )

    def add_dataobject_annotations(cls, unsafe: bool, validate: bool, schema: bool):
        setattr(
            cls,
            "__data_object__",
            {"unsafe": unsafe, "validate": validate, "schema": schema},
        )
        setattr(cls, "__stream_event__", StreamEventParams(None, None))
        setattr(cls, "event_id", StreamEventMixin.event_id)
        setattr(cls, "event_ts", StreamEventMixin.event_ts)

    def set_fields_optional(cls):
        for field in fields(cls):
            field.default = None

    def wrap(cls) -> Type[DataFrameMixin]:
        if hasattr(cls, "__dataframe__"):
            return cls
        amended_class = add_dataframe_mixin(cls)
        add_dataframe_metadata(amended_class)
        add_dataobject_annotations(amended_class, unsafe, validate, schema)
        set_fields_optional(amended_class)
        return amended_class

    if decorated_class is None:
        return wrap
    return wrap(decorated_class)  # type: ignore


class DataFrame(DataFrameMixin, Generic[DataFrameType]):
    def __new__(cls, obj: DataFrameType):
        return obj
