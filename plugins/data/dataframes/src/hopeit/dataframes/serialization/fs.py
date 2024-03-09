from importlib import import_module
import io
import os
from typing import Callable, Generic, Optional, Type, TypeVar, Union
from uuid import uuid4
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
        self.location = location

        settings = FileStorageSettings(
            path=location,
            partition_dateformat=partition_dateformat or "%Y/%m/%d/%H/",
        )
        if self.store is None:
            self.store = FileStorage.with_settings(settings)

    async def save(self, dataframe: DataFrameType) -> Dataset:
        datatype = type(dataframe)
        partition_key = _get_partition_key(self.partition_dateformat)
        path = self.base_path / partition_key
        key = f"{datatype.__qualname__.lower()}_{uuid4()}.parquet"
        os.makedirs(path.resolve().as_posix(), exist_ok=True)
        location = path / key

        async with aiofiles.open(location, "wb") as f:
            await f.write(dataframe._df.to_parquet(engine="pyarrow"))

        # data = io.BytesIO(dataframe._df.to_parquet(engine="pyarrow"))
        # location = await self.fs_storage.store_file(file_name=key, value=data)
        # partition_key = self.fs_storage.partition_key(location)

        return Dataset(
            protocol=f"{__name__}.DatasetFsStorage",
            partition_key=partition_key,
            key=key,
            datatype=f"{datatype.__module__}.{datatype.__qualname__}",
        )

    async def load(self, dataset: Dataset) -> EventPayloadType:
        datatype: Type[DataFrameType] = find_dataframe_type(dataset.datatype)
        location = self.base_path / dataset.partition_key / dataset.key
        async with aiofiles.open(location, "rb") as f:
            df = pd.read_parquet(io.BytesIO(await f.read()), engine="pyarrow")
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

    def _get_patition_key(self, location: str) -> str:
        return location.replace(self.store.path.as_posix(), "")[1:]


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
