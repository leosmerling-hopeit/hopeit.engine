from importlib import import_module
import io
import os
from typing import Callable, Generic, Optional, Type, TypeVar, Union
from uuid import uuid4
import aiofiles
from hopeit.dataframes.dataframe import DataFrameMixin

import pandas as pd
from hopeit.dataframes.serialization.dataset import Dataset
from hopeit.dataobjects import EventPayloadType

from hopeit.fs_storage import FileStorage, FileStorageSettings

DataFrameType = TypeVar("DataFrameType", bound=DataFrameMixin)


class DatasetFsStorage(Generic[DataFrameType]):
    store: Optional[FileStorage] = None
    location: Optional[str] = None

    def __init__(self, *, location: str, partition_dateformat: Optional[str], **kwargs):
        settings = FileStorageSettings(
            path=location,
            partition_dateformat=partition_dateformat or "%Y/%m/%d/%H/",
        )
        if self.store is None:
            self.store = FileStorage.with_settings(settings)

    async def save(self, dataframe: DataFrameType) -> Dataset:
        datatype = type(dataframe)
        key = f"{datatype.__qualname__.lower()}_{uuid4()}.parquet"
        data = io.BytesIO(dataframe._df.to_parquet(engine="pyarrow"))
        location = await self.store.store_file(key, data)
        partition_key = self.store.partition_key(location)

        return Dataset(
            protocol=f"{__name__}.DatasetFsStorage",
            partition_key=partition_key,
            key=key,
            datatype=f"{datatype.__module__}.{datatype.__qualname__}",
        )

    async def load(self, dataset: Dataset) -> DataFrameType:
        datatype = find_dataframe_type(dataset.datatype)
        data = await self.store.get_file(file_name=dataset.key, partition_key=dataset.partition_key)
        df = pd.read_parquet(io.BytesIO(data), engine="pyarrow")
        return datatype._from_df(df)

    async def ser_wrapper(
        self,
        base_serialization: Callable,
        data: Union[EventPayloadType, DataFrameType],
        level: int,
    ) -> bytes:
        if hasattr(data, "__dataframeobject__"):
            data = await data._serialize()  # type: ignore
        if hasattr(data, "__dataframe__"):
            data = await self.save(data)  # type: ignore
        return await base_serialization(data, level)

    async def deser_wrapper(
        self,
        base_deserialization: Callable,
        data: bytes,
        datatype: Union[Type[EventPayloadType], Type[DataFrameType]],
    ) -> Union[EventPayloadType, DataFrameType]:
        if hasattr(datatype, "__dataframeobject__"):
            dataset = await base_deserialization(
                data, datatype.__dataframeobject__.serialized_type  # type: ignore
            )
            return await datatype._deserialize(dataset)  # type: ignore
        if hasattr(datatype, "__dataframe__"):
            dataset = await base_deserialization(data, Dataset)
            return await self.load(dataset)
        return await base_deserialization(data, datatype)


def find_dataframe_type(qual_type_name: str) -> Type[DataFrameType]:
    mod_name, type_name = (
        ".".join(qual_type_name.split(".")[:-1]),
        qual_type_name.split(".")[-1],
    )
    module = import_module(mod_name)
    datatype = getattr(module, type_name)
    assert hasattr(
        datatype, "__dataframe__"
    ), f"Type {qual_type_name} must be annotated with `@dataframe`."
    return datatype
